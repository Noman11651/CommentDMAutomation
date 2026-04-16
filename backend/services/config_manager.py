import json
import os
from typing import Any, Optional, Tuple

import requests

REDIS_CONFIG_KEY = os.environ.get("REELS_CONFIG_KV_KEY", "commentdm:reels_config_v1")
SUPABASE_TABLE = os.environ.get("SUPABASE_CONFIG_TABLE", "reels_config")
SUPABASE_KEY_COLUMN = os.environ.get("SUPABASE_CONFIG_KEY_COLUMN", "config_key")
SUPABASE_VALUE_COLUMN = os.environ.get("SUPABASE_CONFIG_VALUE_COLUMN", "config_value")
SUPABASE_CONFIG_KEY = os.environ.get("SUPABASE_CONFIG_KEY", "default")


def _backend_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_file_path():
    explicit = os.environ.get("CONFIG_FILE_PATH", "").strip()
    if explicit:
        return explicit
    if os.environ.get("VERCEL"):
        return "/tmp/reels_config.json"
    return os.path.join(_backend_dir(), "reels_config.json")


CONFIG_FILE = _config_file_path()


def _default_config() -> dict[str, Any]:
    return {
        "reels": {},
        "default": {
            "trigger_keyword": "info",
            "dm_message": "Thanks for your interest! Check your DMs.",
            "comment_reply": "Sent you a DM!",
            "active": True,
        },
    }


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
    # explicit override
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
                "CONFIG_STORAGE=redis but KV_REST_API_URL / KV_REST_API_TOKEN "
                "(or Upstash REST URL/token) are missing"
            )
        return "redis"

    # auto-detect: prefer Supabase if configured, else Redis, else file
    base_url, service_key = _supabase_credentials()
    if base_url and service_key:
        return "supabase"
    url, token = _kv_credentials()
    if url and token:
        return "redis"
    return "file"


def _redis_command(command: list) -> dict:
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


def _redis_get_json() -> Optional[dict]:
    data = _redis_command(["GET", REDIS_CONFIG_KEY])
    raw = data.get("result")
    if raw is None:
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    raise RuntimeError("Unexpected KV GET result type")


def _redis_set_json(config: dict) -> None:
    payload = json.dumps(config, separators=(",", ":"))
    _redis_command(["SET", REDIS_CONFIG_KEY, payload])


def _supabase_table_url() -> str:
    base_url, _ = _supabase_credentials()
    return f"{base_url}/rest/v1/{SUPABASE_TABLE}"


def _supabase_headers(prefer: Optional[str] = None) -> dict:
    _, service_key = _supabase_credentials()
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_get_json() -> Optional[dict]:
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


def _supabase_set_json(config: dict) -> None:
    row = {SUPABASE_KEY_COLUMN: SUPABASE_CONFIG_KEY, SUPABASE_VALUE_COLUMN: config}
    response = requests.post(
        _supabase_table_url(),
        params={"on_conflict": SUPABASE_KEY_COLUMN},
        headers=_supabase_headers(prefer="resolution=merge-duplicates,return=minimal"),
        json=[row],
        timeout=15,
    )
    response.raise_for_status()


def _save_config_file(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _bootstrap_file_paths():
    paths = []
    extra = os.environ.get("CONFIG_BOOTSTRAP_FILE", "").strip()
    if extra:
        paths.append(extra)
    paths.append(os.path.join(_backend_dir(), "reels_config.json"))
    if os.environ.get("VERCEL"):
        paths.append("/tmp/reels_config.json")
    return paths


def _try_bootstrap_from_file() -> Optional[dict]:
    for path in _bootstrap_file_paths():
        if path and os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _load_config():
    backend = _storage_backend()
    if backend == "redis":
        try:
            cfg = _redis_get_json()
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis read failed: {e}") from e
        if cfg is None:
            migrated = _try_bootstrap_from_file()
            if migrated is not None:
                _redis_set_json(migrated)
                return migrated
            default_config = _default_config()
            _redis_set_json(default_config)
            return default_config
        return cfg

    if backend == "supabase":
        try:
            cfg = _supabase_get_json()
        except requests.RequestException as e:
            raise RuntimeError(f"Supabase read failed: {e}") from e
        if cfg is None:
            migrated = _try_bootstrap_from_file()
            if migrated is not None:
                _supabase_set_json(migrated)
                return migrated
            default_config = _default_config()
            _supabase_set_json(default_config)
            return default_config
        return cfg

    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
        _save_config_file(default_config)
        return default_config
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    backend = _storage_backend()
    if backend == "redis":
        try:
            _redis_set_json(config)
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis write failed: {e}") from e
        return
    if backend == "supabase":
        try:
            _supabase_set_json(config)
        except requests.RequestException as e:
            raise RuntimeError(f"Supabase write failed: {e}") from e
        return
    _save_config_file(config)


def get_all_configs():
    return _load_config()


def get_reel_config(media_id: str):
    config = _load_config()
    return config["reels"].get(media_id, config["default"])


def update_reel_config(media_id: str, new_config: dict):
    config = _load_config()
    config["reels"][media_id] = new_config
    _save_config(config)
    return new_config
