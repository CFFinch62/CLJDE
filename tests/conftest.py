"""Shared pytest fixtures for the CLJDE test suite.

Currently this file only exists to mark the ``tests/`` directory as a
pytest rootdir and to isolate tests from the developer's real config
directory by pointing ``XDG_CONFIG_HOME`` at a per-session tmpdir
before any CLJDE module is imported.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect CLJDE's config directory to a per-test tmpdir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("APPDATA", raising=False)
    return tmp_path / "cljde"


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root (one level above ``tests/``)."""
    return Path(__file__).resolve().parent.parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Placeholder hook kept so future phases can mark slow/GUI tests."""
    del config, items
