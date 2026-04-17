"""Persistent application settings for CLIDE.

Settings live in a JSON file inside the per-user config directory
resolved by :mod:`clide.config.paths`. The file is auto-created with
sensible defaults on first run. Geometry and dock state are stored as
base64-encoded strings because QByteArray is not directly JSON-safe.
"""

from __future__ import annotations

import base64
import copy
import json
import logging
from typing import Any

from PyQt6.QtCore import QByteArray

from clide.config.paths import settings_path

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "window": {
        "geometry": "",
        "state": "",
        "width": 1400,
        "height": 900,
    },
    "theme": {
        "name": "default",
    },
    "editor": {
        "font_family": "monospace",
        "font_size": 11,
        "tab_width": 2,
        "rainbow_parens": False,
    },
    "repl": {
        "lein_command": "lein repl :headless :host 127.0.0.1",
        "clj_command": "clj -M:nrepl",
        "default_host": "127.0.0.1",
        "default_port": 0,
        "max_history_lines": 5000,
    },
    "files": {
        "last_project_path": "",
        "recent_files": [],
        "open_tabs": [],
        "current_tab_index": 0,
        "show_hidden": False,
        "max_recent": 10,
    },
}


class Settings:
    """In-memory settings mirror with load/save support."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from disk, creating defaults if missing or corrupt."""
        path = settings_path()
        if not path.exists():
            log.info("No settings file at %s; writing defaults.", path)
            inst = cls(copy.deepcopy(DEFAULT_SETTINGS))
            inst.save()
            return inst
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to read settings %s (%s); using defaults.", path, exc)
            return cls(copy.deepcopy(DEFAULT_SETTINGS))
        merged = _merge_defaults(copy.deepcopy(DEFAULT_SETTINGS), data)
        return cls(merged)

    def save(self) -> None:
        """Persist the current settings to disk."""
        path = settings_path()
        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
        except OSError as exc:
            log.error("Failed to write settings %s: %s", path, exc)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Return a nested setting value, falling back to ``default``."""
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Write a nested setting value, creating the section if absent."""
        self._data.setdefault(section, {})[key] = value

    def section(self, name: str) -> dict[str, Any]:
        """Return the mutable mapping for a named section."""
        return self._data.setdefault(name, {})

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the underlying dictionary."""
        return dict(self._data)

    def set_window_geometry(self, geometry: QByteArray) -> None:
        """Store a QByteArray of window geometry as base64."""
        self.set("window", "geometry", _qba_to_b64(geometry))

    def window_geometry(self) -> QByteArray:
        """Return the saved window geometry as a QByteArray."""
        return _b64_to_qba(self.get("window", "geometry", ""))

    def set_window_state(self, state: QByteArray) -> None:
        """Store a QByteArray of dock/toolbar state as base64."""
        self.set("window", "state", _qba_to_b64(state))

    def window_state(self) -> QByteArray:
        """Return the saved dock/toolbar state as a QByteArray."""
        return _b64_to_qba(self.get("window", "state", ""))


def _merge_defaults(defaults: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """Recursively overlay ``user`` onto ``defaults`` without losing keys."""
    out = defaults
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_defaults(out[key], value)
        else:
            out[key] = value
    return out


def _qba_to_b64(data: QByteArray) -> str:
    """Encode a QByteArray as a base64 ASCII string."""
    if data is None or data.isEmpty():
        return ""
    return base64.b64encode(bytes(data)).decode("ascii")


def _b64_to_qba(encoded: str) -> QByteArray:
    """Decode a base64 string into a QByteArray (empty on failure)."""
    if not encoded:
        return QByteArray()
    try:
        return QByteArray(base64.b64decode(encoded.encode("ascii")))
    except (ValueError, TypeError):
        return QByteArray()
