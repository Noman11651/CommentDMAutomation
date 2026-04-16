import json
import os
from typing import Any, Optional, Tuple

import requests

REDIS_CONFIG_KEY = os.environ.get("REELS_CONFIG_KV_KEY", "commentdm:reels_config_v1")


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


def _use_redis() -> bool:
    mode = os.environ.get("CONFIG_STORAGE", "").strip().lower()
    if mode == "file":
        return False
    if mode == "redis":
        url, token = _kv_credentials()
        if not url or not token:
            raise RuntimeError(
                "CONFIG_STORAGE=redis but KV_REST_API_URL / KV_REST_API_TOKEN "
                "(or Upstash REST URL/token) are missing"
            )
        return True
    url, token = _kv_credentials()
    return bool(url and token)


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


def _load_config_file() -> dict:
    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
        _save_config_file(default_config)
        return default_config
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


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


def _try_bootstrap_redis_from_file() -> Optional[dict]:
    for path in _bootstrap_file_paths():
        if path and os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _load_config():
    if _use_redis():
        try:
            cfg = _redis_get_json()
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis read failed: {e}") from e
        if cfg is None:
            migrated = _try_bootstrap_redis_from_file()
            if migrated is not None:
                _redis_set_json(migrated)
                return migrated
            default_config = _default_config()
            _redis_set_json(default_config)
            return default_config
        return cfg

    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
        _save_config_file(default_config)
        return default_config
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    if _use_redis():
        try:
            _redis_set_json(config)
        except requests.RequestException as e:
            raise RuntimeError(f"KV/Redis write failed: {e}") from e
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
