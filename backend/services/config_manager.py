import json
import os

def _backend_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_file_path():
    explicit = os.environ.get("CONFIG_FILE_PATH", "").strip()
    if explicit:
        return explicit
    # Vercel serverless (and similar) only allow writes under /tmp
    if os.environ.get("VERCEL"):
        return "/tmp/reels_config.json"
    return os.path.join(_backend_dir(), "reels_config.json")


CONFIG_FILE = _config_file_path()

def _load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "reels": {},
            "default": {
                "trigger_keyword": "info",
                "dm_message": "Thanks for your interest! Check your DMs.",
                "comment_reply": "Sent you a DM!",
                "active": True
            }
        }
        _save_config(default_config)
        return default_config
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def _save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

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
