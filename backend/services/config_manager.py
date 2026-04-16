import json
import os
import time
import uuid
from copy import deepcopy
from typing import Any, Callable, Optional, Tuple

import requests

REDIS_CONFIG_KEY = os.environ.get("REELS_CONFIG_KV_KEY", "commentdm:reels_config_v1")
SUPABASE_TABLE = os.environ.get("SUPABASE_CONFIG_TABLE", "reels_config")
SUPABASE_KEY_COLUMN = os.environ.get("SUPABASE_CONFIG_KEY_COLUMN", "config_key")
SUPABASE_VALUE_COLUMN = os.environ.get("SUPABASE_CONFIG_VALUE_COLUMN", "config_value")
SUPABASE_CONFIG_KEY = os.environ.get("SUPABASE_CONFIG_KEY", "default")
DM_RATE_LIMIT_PER_HOUR = int(os.environ.get("DM_RATE_LIMIT_PER_HOUR", "200"))
MAX_ANALYTICS_EVENTS = int(os.environ.get("MAX_ANALYTICS_EVENTS", "5000"))
MAX_DEDUP_KEYS = int(os.environ.get("MAX_DEDUP_KEYS", "5000"))


def _backend_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_file_path() -> str:
    explicit = os.environ.get("CONFIG_FILE_PATH", "").strip()
    if explicit:
        return explicit
    if os.environ.get("VERCEL"):
        return "/tmp/reels_config.json"
    return os.path.join(_backend_dir(), "reels_config.json")


CONFIG_FILE = _config_file_path()


def _default_reel_config() -> dict[str, Any]:
    return {
        "trigger_keyword": "",
        "dm_message": "",
        "comment_reply": "",
        "active": False,
        "flow_id": "",
    }


def _default_config() -> dict[str, Any]:
    return {
        "reels": {},
        "default": _default_reel_config(),
        "flows": {},
        "contacts": {},
        "dedup": {},
        "queue": {"pending": [], "history": []},
        "rate_limit": {"sent_timestamps": []},
        "analytics": {"events": []},
    }


def _normalize_reel_config(raw: dict[str, Any]) -> dict[str, Any]:
    out = _default_reel_config()
    out.update(raw or {})
    out["trigger_keyword"] = str(out.get("trigger_keyword", "")).strip()
    out["dm_message"] = str(out.get("dm_message", "")).strip()
    out["comment_reply"] = str(out.get("comment_reply", "")).strip()
    out["flow_id"] = str(out.get("flow_id", "")).strip()
    out["active"] = bool(out.get("active", False))
    return out


def _normalize_config_schema(config: dict[str, Any]) -> dict[str, Any]:
    base = _default_config()
    merged = deepcopy(base)
    if isinstance(config, dict):
        merged.update(config)

    merged["default"] = _normalize_reel_config(merged.get("default", {}))
    reels = merged.get("reels", {})
    if not isinstance(reels, dict):
        reels = {}
    merged["reels"] = {
        str(media_id): _normalize_reel_config(reel_cfg)
        for media_id, reel_cfg in reels.items()
        if isinstance(reel_cfg, dict)
    }

    for key in ("flows", "contacts", "dedup"):
        if not isinstance(merged.get(key), dict):
            merged[key] = {}

    queue = merged.get("queue", {})
    if not isinstance(queue, dict):
        queue = {}
    queue.setdefault("pending", [])
    queue.setdefault("history", [])
    if not isinstance(queue["pending"], list):
        queue["pending"] = []
    if not isinstance(queue["history"], list):
        queue["history"] = []
    merged["queue"] = queue

    rate_limit = merged.get("rate_limit", {})
    if not isinstance(rate_limit, dict):
        rate_limit = {}
    rate_limit.setdefault("sent_timestamps", [])
    if not isinstance(rate_limit["sent_timestamps"], list):
        rate_limit["sent_timestamps"] = []
    merged["rate_limit"] = rate_limit

    analytics = merged.get("analytics", {})
    if not isinstance(analytics, dict):
        analytics = {}
    analytics.setdefault("events", [])
    if not isinstance(analytics["events"], list):
        analytics["events"] = []
    merged["analytics"] = analytics

    return merged


def _supabase_credentials() -> Tuple[str, str]:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return base_url, service_key


def _kv_credentials() -> Tuple[str, str]:
    url = (
        os.environ.get("KV_REST_API_URL")
        or os.environ.get("UPSTASH_REDIS_REST_URL")
        or ""
    ).rstrip("/")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get(
        "UPSTASH_REDIS_REST_TOKEN", ""
    )
    return url, token


def _storage_backend() -> str:
    mode = os.environ.get("CONFIG_STORAGE", "").strip().lower()
    if mode == "file":
        return "file"
    if mode == "supabase":
        base_url, service_key = _supabase_credentials()
        if not base_url or not service_key:
            raise RuntimeError(
                "CONFIG_STORAGE=supabase but SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are missing"
            )
        return "supabase"
    if mode == "redis":
        url, token = _kv_credentials()
        if not url or not token:
            raise RuntimeError(
                "CONFIG_STORAGE=redis but KV_REST_API_URL / KV_REST_API_TOKEN (or Upstash REST URL/token) are missing"
            )
        return "redis"

    base_url, service_key = _supabase_credentials()
    if base_url and service_key:
        return "supabase"
    url, token = _kv_credentials()
    if url and token:
        return "redis"
    return "file"


def _redis_command(command: list[Any]) -> dict[str, Any]:
    url, token = _kv_credentials()
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=command,
        timeout=15,
    )
    r.raise_for_status()
    out = r.json()
    if out.get("error"):
        raise RuntimeError(str(out["error"]))
    return out


def _redis_get_json() -> Optional[dict[str, Any]]:
    data = _redis_command(["GET", REDIS_CONFIG_KEY])
    raw = data.get("result")
    if raw is None:
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    raise RuntimeError("Unexpected KV GET result type")


def _redis_set_json(config: dict[str, Any]) -> None:
    payload = json.dumps(config, separators=(",", ":"))
    _redis_command(["SET", REDIS_CONFIG_KEY, payload])


def _supabase_table_url() -> str:
    base_url, _ = _supabase_credentials()
    return f"{base_url}/rest/v1/{SUPABASE_TABLE}"


def _supabase_headers(prefer: Optional[str] = None) -> dict[str, str]:
    _, service_key = _supabase_credentials()
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_get_json() -> Optional[dict[str, Any]]:
    params = {
        SUPABASE_KEY_COLUMN: f"eq.{SUPABASE_CONFIG_KEY}",
        "select": SUPABASE_VALUE_COLUMN,
        "limit": 1,
    }
    response = requests.get(
        _supabase_table_url(),
        params=params,
        headers=_supabase_headers(),
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        return None
    row = payload[0]
    value = row.get(SUPABASE_VALUE_COLUMN)
    if isinstance(value, dict):
        return value
    raise RuntimeError(f"Unexpected Supabase value type: {type(value).__name__}")


def _supabase_set_json(config: dict[str, Any]) -> None:
    row = {SUPABASE_KEY_COLUMN: SUPABASE_CONFIG_KEY, SUPABASE_VALUE_COLUMN: config}
    response = requests.post(
        _supabase_table_url(),
        params={"on_conflict": SUPABASE_KEY_COLUMN},
        headers=_supabase_headers(prefer="resolution=merge-duplicates,return=minimal"),
        json=[row],
        timeout=15,
    )
    response.raise_for_status()


def _save_config_file(config: dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _bootstrap_file_paths() -> list[str]:
    paths: list[str] = []
    extra = os.environ.get("CONFIG_BOOTSTRAP_FILE", "").strip()
    if extra:
        paths.append(extra)
    paths.append(os.path.join(_backend_dir(), "reels_config.json"))
    if os.environ.get("VERCEL"):
        paths.append("/tmp/reels_config.json")
    return paths


def _try_bootstrap_from_file() -> Optional[dict[str, Any]]:
    for path in _bootstrap_file_paths():
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _load_config() -> dict[str, Any]:
    backend = _storage_backend()
    if backend == "redis":
        try:
            cfg = _redis_get_json()
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis read failed: {e}") from e
        if cfg is None:
            cfg = _try_bootstrap_from_file() or _default_config()
            _redis_set_json(_normalize_config_schema(cfg))
            return _normalize_config_schema(cfg)
        return _normalize_config_schema(cfg)

    if backend == "supabase":
        try:
            cfg = _supabase_get_json()
        except requests.RequestException as e:
            raise RuntimeError(f"Supabase read failed: {e}") from e
        if cfg is None:
            cfg = _try_bootstrap_from_file() or _default_config()
            _supabase_set_json(_normalize_config_schema(cfg))
            return _normalize_config_schema(cfg)
        return _normalize_config_schema(cfg)

    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
        _save_config_file(default_config)
        return default_config
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return _normalize_config_schema(json.load(f))


def _save_config(config: dict[str, Any]) -> None:
    normalized = _normalize_config_schema(config)
    backend = _storage_backend()
    if backend == "redis":
        try:
            _redis_set_json(normalized)
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis write failed: {e}") from e
        return
    if backend == "supabase":
        try:
            _supabase_set_json(normalized)
        except requests.RequestException as e:
            raise RuntimeError(f"Supabase write failed: {e}") from e
        return
    _save_config_file(normalized)


def _update_config(mutator: Callable[[dict[str, Any]], Any]) -> Any:
    config = _load_config()
    result = mutator(config)
    _save_config(config)
    return result


def _now_ts() -> int:
    return int(time.time())


def _compact_dedup(config: dict[str, Any]) -> None:
    dedup = config["dedup"]
    if len(dedup) <= MAX_DEDUP_KEYS:
        return
    items = sorted(dedup.items(), key=lambda kv: kv[1], reverse=True)[:MAX_DEDUP_KEYS]
    config["dedup"] = {k: v for k, v in items}


def _compact_analytics(config: dict[str, Any]) -> None:
    events = config["analytics"]["events"]
    if len(events) > MAX_ANALYTICS_EVENTS:
        config["analytics"]["events"] = events[-MAX_ANALYTICS_EVENTS:]


def get_all_configs() -> dict[str, Any]:
    return _load_config()


def get_reel_config(media_id: str) -> dict[str, Any]:
    config = _load_config()
    return config["reels"].get(media_id, config["default"])


def is_reel_configured(media_id: str) -> bool:
    config = _load_config()
    return media_id in config["reels"]


def update_reel_config(media_id: str, new_config: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_reel_config(new_config)

    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        config["reels"][media_id] = normalized
        return normalized

    return _update_config(_mutate)


def get_flow(flow_id: str) -> Optional[dict[str, Any]]:
    config = _load_config()
    return config["flows"].get(flow_id)


def list_flows() -> list[dict[str, Any]]:
    config = _load_config()
    return list(config["flows"].values())


def upsert_flow(flow_data: dict[str, Any]) -> dict[str, Any]:
    flow_id = str(flow_data.get("id") or "").strip() or str(uuid.uuid4())
    name = str(flow_data.get("name") or "Untitled Flow").strip()
    steps = flow_data.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    normalized = {"id": flow_id, "name": name, "steps": steps, "updated_at": _now_ts()}

    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        config["flows"][flow_id] = normalized
        return normalized

    return _update_config(_mutate)


def get_contact(sender_id: str) -> Optional[dict[str, Any]]:
    config = _load_config()
    return config["contacts"].get(sender_id)


def upsert_contact(sender_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    sender_id = str(sender_id)

    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        base = config["contacts"].get(sender_id, {"sender_id": sender_id, "follow_confirmed": False})
        base.update(patch or {})
        base["updated_at"] = _now_ts()
        config["contacts"][sender_id] = base
        return base

    return _update_config(_mutate)


def clear_contact_state(sender_id: str) -> None:
    upsert_contact(sender_id, {"state": {}, "awaiting_map": {}})


def record_analytics(event_type: str, **payload: Any) -> dict[str, Any]:
    event = {"ts": _now_ts(), "type": event_type}
    event.update(payload)

    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        config["analytics"]["events"].append(event)
        _compact_analytics(config)
        return event

    return _update_config(_mutate)


def check_and_mark_dedup(sender_id: str, media_id: str, trigger_keyword: str) -> bool:
    key = f"{sender_id}|{media_id}|{trigger_keyword.lower()}"
    now = _now_ts()

    def _mutate(config: dict[str, Any]) -> bool:
        exists = key in config["dedup"]
        if not exists:
            config["dedup"][key] = now
            _compact_dedup(config)
        return not exists

    return _update_config(_mutate)


def enqueue_dm(
    recipient: str,
    recipient_type: str,
    payload_type: str,
    payload: dict[str, Any],
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    job = {
        "id": str(uuid.uuid4()),
        "recipient": recipient,
        "recipient_type": recipient_type,  # "comment_id" or "id"
        "payload_type": payload_type,  # "text", "quick_replies", "button_template"
        "payload": payload,
        "metadata": metadata or {},
        "created_at": _now_ts(),
        "status": "pending",
    }

    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        config["queue"]["pending"].append(job)
        return job

    return _update_config(_mutate)


def get_queue_status() -> dict[str, Any]:
    config = _load_config()
    pending = config["queue"]["pending"]
    history = config["queue"]["history"]
    sent_timestamps = _pruned_sent_timestamps(config["rate_limit"]["sent_timestamps"])
    return {
        "pending": len(pending),
        "history": len(history),
        "sent_last_hour": len(sent_timestamps),
        "rate_limit_per_hour": DM_RATE_LIMIT_PER_HOUR,
    }


def _pruned_sent_timestamps(timestamps: list[int]) -> list[int]:
    cutoff = _now_ts() - 3600
    return [ts for ts in timestamps if ts >= cutoff]


def process_dm_queue(send_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    def _mutate(config: dict[str, Any]) -> dict[str, Any]:
        sent_timestamps = _pruned_sent_timestamps(config["rate_limit"]["sent_timestamps"])
        pending = config["queue"]["pending"]
        history = config["queue"]["history"]
        sent = 0
        failed = 0
        queued_due_rate_limit = 0
        kept: list[dict[str, Any]] = []

        for job in pending:
            if len(sent_timestamps) >= DM_RATE_LIMIT_PER_HOUR:
                kept.append(job)
                queued_due_rate_limit += 1
                config["analytics"]["events"].append(
                    {
                        "ts": _now_ts(),
                        "type": "dm_queued_rate_limit",
                        "job_id": job.get("id"),
                        "recipient": job.get("recipient"),
                    }
                )
                continue
            result = send_fn(job)
            if result.get("error"):
                job["status"] = "failed"
                job["result"] = result
                job["processed_at"] = _now_ts()
                history.append(job)
                failed += 1
                config["analytics"]["events"].append(
                    {
                        "ts": _now_ts(),
                        "type": "dm_failed",
                        "job_id": job.get("id"),
                        "recipient": job.get("recipient"),
                    }
                )
            else:
                job["status"] = "sent"
                job["result"] = result
                job["processed_at"] = _now_ts()
                history.append(job)
                sent += 1
                sent_timestamps.append(_now_ts())
                config["analytics"]["events"].append(
                    {
                        "ts": _now_ts(),
                        "type": "dm_sent",
                        "job_id": job.get("id"),
                        "recipient": job.get("recipient"),
                    }
                )

        config["queue"]["pending"] = kept
        config["queue"]["history"] = history[-1000:]
        config["rate_limit"]["sent_timestamps"] = sent_timestamps
        _compact_analytics(config)
        return {
            "sent": sent,
            "failed": failed,
            "remaining": len(kept),
            "queued_due_rate_limit": queued_due_rate_limit,
        }

    return _update_config(_mutate)


def get_analytics_summary() -> dict[str, Any]:
    config = _load_config()
    events = config["analytics"]["events"]
    summary = {
        "events_total": len(events),
        "triggers_matched": 0,
        "dms_sent": 0,
        "dm_failed": 0,
        "comment_replies_sent": 0,
        "dedup_skips": 0,
        "rate_limited_queued": 0,
        "quick_reply_responses": 0,
        "flow_steps_executed": 0,
    }
    for event in events:
        t = event.get("type")
        if t == "trigger_matched":
            summary["triggers_matched"] += 1
        elif t == "dm_sent":
            summary["dms_sent"] += 1
        elif t == "dm_failed":
            summary["dm_failed"] += 1
        elif t == "comment_reply_sent":
            summary["comment_replies_sent"] += 1
        elif t == "dedup_skip":
            summary["dedup_skips"] += 1
        elif t == "dm_queued_rate_limit":
            summary["rate_limited_queued"] += 1
        elif t == "quick_reply_response":
            summary["quick_reply_responses"] += 1
        elif t == "flow_step_executed":
            summary["flow_steps_executed"] += 1
    return summary
