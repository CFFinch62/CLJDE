"""Phase 1 smoke tests: package imports and core helpers work.

These are deliberately trivial. Their job is to confirm the test
harness itself works end-to-end so that Phase 2 tests (which actually
exercise logic) have somewhere to land.
"""

from __future__ import annotations

import json
from pathlib import Path

from clide import __version__
from clide.config import paths, settings, theme


def test_version_is_nonempty() -> None:
    """The package exposes a semantic-ish version string."""
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 1


def test_config_dir_is_under_tmpdir(_isolated_config_dir: Path) -> None:
    """``config_dir`` honours ``XDG_CONFIG_HOME``."""
    resolved = paths.config_dir()
    assert resolved == _isolated_config_dir


def test_settings_roundtrip() -> None:
    """Saving and reloading settings preserves custom values."""
    s = settings.Settings.load()
    s.set("editor", "font_size", 13)
    s.save()

    reloaded = settings.Settings.load()
    assert reloaded.get("editor", "font_size") == 13

    raw = json.loads(paths.settings_path().read_text(encoding="utf-8"))
    assert raw["editor"]["font_size"] == 13


def test_stylesheet_builds_nonempty() -> None:
    """The QSS builder returns a non-trivial string."""
    qss = theme.build_stylesheet()
    assert isinstance(qss, str)
    assert "QMainWindow" in qss
    assert theme.DEFAULT_PALETTE.amber_primary in qss


def test_bundled_default_theme_resolves() -> None:
    """The bundled default.json theme file exists on disk."""
    path = paths.bundled_theme_path("default")
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["palette"]["amber_primary"] == theme.DEFAULT_PALETTE.amber_primary
