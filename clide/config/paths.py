"""Platform-aware configuration path resolution for CLIDE.

Provides the config directory and well-known file paths used by the rest
of the application. On Linux the XDG specification is honoured; macOS
and Windows use their conventional per-user application data locations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "clide"

SETTINGS_FILENAME = "settings.json"
LOG_FILENAME = "clide.log"
SESSION_CACHE_FILENAME = "session.json"
THEME_OVERRIDE_FILENAME = "theme.json"


def config_dir() -> Path:
    """Return the per-user configuration directory for CLIDE."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME


def ensure_config_dir() -> Path:
    """Create the config directory if needed and return its path."""
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    """Return the absolute path to the settings JSON file."""
    return ensure_config_dir() / SETTINGS_FILENAME


def log_path() -> Path:
    """Return the absolute path to the rotating log file."""
    return ensure_config_dir() / LOG_FILENAME


def session_cache_path() -> Path:
    """Return the absolute path to the session cache JSON file."""
    return ensure_config_dir() / SESSION_CACHE_FILENAME


def theme_override_path() -> Path:
    """Return the absolute path to the user theme override file."""
    return ensure_config_dir() / THEME_OVERRIDE_FILENAME


def bundled_theme_path(name: str = "default") -> Path:
    """Return the path to a theme JSON bundled inside the package."""
    return Path(__file__).resolve().parent.parent / "resources" / "themes" / f"{name}.json"
