"""
Configuration and keychain management for Claude Usage Tracker.
"""

import subprocess
import json
import os
from pathlib import Path

SERVICE_NAME = "claude-usage-tracker"
ACCOUNT_NAME = "admin-api-key"
CONFIG_DIR = Path.home() / ".config" / "claude-usage-tracker"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default settings
DEFAULT_CONFIG = {
    "refresh_interval_minutes": 5,
    "show_cost_in_menubar": True,
    "default_timeframe": "today",
}


def get_keychain_key() -> str | None:
    """Retrieve the Admin API key from macOS Keychain."""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s", SERVICE_NAME,
                "-a", ACCOUNT_NAME,
                "-w",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def set_keychain_key(api_key: str) -> bool:
    """Store the Admin API key in macOS Keychain."""
    try:
        # First, try to delete any existing entry
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s", SERVICE_NAME,
                "-a", ACCOUNT_NAME,
            ],
            capture_output=True,
        )

        # Add the new key
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-s", SERVICE_NAME,
                "-a", ACCOUNT_NAME,
                "-w", api_key,
            ],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def delete_keychain_key() -> bool:
    """Remove the Admin API key from macOS Keychain."""
    try:
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s", SERVICE_NAME,
                "-a", ACCOUNT_NAME,
            ],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_api_key() -> str | None:
    """Get API key from keychain, env var, or config file."""
    # Try keychain first
    key = get_keychain_key()
    if key:
        return key

    # Try environment variable
    key = os.environ.get("ANTHROPIC_ADMIN_API_KEY")
    if key:
        return key

    # Try config file
    config = load_config()
    return config.get("admin_api_key")


def load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **config}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Save configuration to file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def get_refresh_interval() -> int:
    """Get refresh interval in seconds."""
    config = load_config()
    return config.get("refresh_interval_minutes", 5) * 60


def mask_api_key(key: str) -> str:
    """Return a masked version of the API key for display."""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
