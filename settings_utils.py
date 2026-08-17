import json
import os
from dotenv import load_dotenv

load_dotenv()
CONFIG_FILE = os.getenv('CONFIG_FILE', 'config.json')

def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def get_setting(key: str, default: any = None) -> any:
    """Retrieves a setting value by key, returning a default value if not found."""
    return load_settings().get(key, default)


def save_setting(key: str, value: any) -> None:
    """Updates or adds a setting key-value pair and persists it to disk."""
    settings = load_settings()
    settings[key] = value

    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=4)