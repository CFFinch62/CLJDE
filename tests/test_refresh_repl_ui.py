"""Unit tests for :func:`clide.ui.main_window_repl.refresh_repl_ui`.

Exercises the button-state truth table across process states and project
kinds using a real :class:`QToolBar` with named :class:`QAction` entries
plus duck-typed stubs for the rest of the main-window surface the
function touches.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QToolBar

from clide.ui import main_window_repl, toolbar as toolbar_mod


@pytest.fixture(scope="module")
def _qapp() -> QApplication:
    """Provide a module-scoped :class:`QApplication` for widget tests."""
    return QApplication.instance() or QApplication([])


@dataclass
class _FakeProject:
    root: Path
    type: str
    name: str


class _FakePM:
    def __init__(self, state: str) -> None:
        self._state = state

    def state(self) -> str:
        return self._state


class _FakeFileTree:
    def __init__(self, project: _FakeProject | None) -> None:
        self._project = project

    def project(self) -> _FakeProject | None:
        return self._project


class _FakeStatusBar:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def set_repl_status(self, text: str, **kwargs: object) -> None:
        self.calls.append((text, dict(kwargs)))


class _FakeWindow:
    def __init__(
        self,
        toolbar: QToolBar,
        project: _FakeProject | None,
        state: str,
    ) -> None:
        self._toolbar = toolbar
        self._tree = _FakeFileTree(project)
        self._pm = _FakePM(state)
        self._status = _FakeStatusBar()

    def toolbar(self) -> QToolBar:
        return self._toolbar

    def file_tree(self) -> _FakeFileTree:
        return self._tree

    def process_manager(self) -> _FakePM:
        return self._pm

    def status_bar(self) -> _FakeStatusBar:
        return self._status


def _make_toolbar(_qapp: QApplication) -> QToolBar:
    """Build a toolbar with the three named REPL actions, all disabled."""
    tb = QToolBar()
    for name in (
        toolbar_mod.REPL_START_ACTION_NAME,
        toolbar_mod.REPL_STOP_ACTION_NAME,
        toolbar_mod.REPL_RESTART_ACTION_NAME,
    ):
        action = tb.addAction(name)
        action.setObjectName(name)
        action.setEnabled(False)
    return tb


def _enabled(tb: QToolBar) -> dict[str, bool]:
    """Return a name->enabled map for the three REPL actions on ``tb``."""
    from PyQt6.QtGui import QAction

    result: dict[str, bool] = {}
    for name in (
        toolbar_mod.REPL_START_ACTION_NAME,
        toolbar_mod.REPL_STOP_ACTION_NAME,
        toolbar_mod.REPL_RESTART_ACTION_NAME,
    ):
        action = tb.findChild(QAction, name)
        assert action is not None
        result[name] = action.isEnabled()
    return result


@pytest.mark.parametrize(
    ("project_type", "state", "expected"),
    [
        ("lein", "idle",     {"start": True,  "stop": False, "restart": True}),
        ("deps", "idle",     {"start": True,  "stop": False, "restart": True}),
        ("lein", "starting", {"start": False, "stop": True,  "restart": True}),
        ("lein", "running",  {"start": False, "stop": True,  "restart": True}),
        ("lein", "stopping", {"start": False, "stop": False, "restart": False}),
        ("lein", "stopped",  {"start": True,  "stop": False, "restart": True}),
        ("lein", "crashed",  {"start": True,  "stop": False, "restart": True}),
        ("other", "idle",    {"start": False, "stop": False, "restart": False}),
    ],
)
def test_refresh_sets_button_states(
    _qapp: QApplication,
    project_type: str,
    state: str,
    expected: dict[str, bool],
) -> None:
    """Button enabled flags follow the (project_type, process_state) matrix."""
    tb = _make_toolbar(_qapp)
    project = _FakeProject(root=Path("/tmp/p"), type=project_type, name="p")
    window = _FakeWindow(tb, project, state)
    main_window_repl.refresh_repl_ui(window)
    flags = _enabled(tb)
    assert flags[toolbar_mod.REPL_START_ACTION_NAME] is expected["start"]
    assert flags[toolbar_mod.REPL_STOP_ACTION_NAME] is expected["stop"]
    assert flags[toolbar_mod.REPL_RESTART_ACTION_NAME] is expected["restart"]


def test_refresh_without_project_disables_all(_qapp: QApplication) -> None:
    """With no project open, every REPL button stays disabled."""
    tb = _make_toolbar(_qapp)
    window = _FakeWindow(tb, None, "idle")
    main_window_repl.refresh_repl_ui(window)
    flags = _enabled(tb)
    assert all(v is False for v in flags.values())


def test_refresh_crashed_state_sets_status_error(_qapp: QApplication) -> None:
    """The crashed state writes a red ``REPL: crashed`` line to the status bar."""
    tb = _make_toolbar(_qapp)
    project = _FakeProject(root=Path("/tmp/p"), type="lein", name="p")
    window = _FakeWindow(tb, project, "crashed")
    main_window_repl.refresh_repl_ui(window)
    assert window._status.calls == [("REPL: crashed", {"error": True})]


def test_refresh_non_crashed_does_not_touch_status(_qapp: QApplication) -> None:
    """Non-crashed transitions leave the status bar untouched by this function."""
    tb = _make_toolbar(_qapp)
    project = _FakeProject(root=Path("/tmp/p"), type="lein", name="p")
    for state in ("idle", "starting", "running", "stopping", "stopped"):
        window = _FakeWindow(tb, project, state)
        main_window_repl.refresh_repl_ui(window)
        assert window._status.calls == []
