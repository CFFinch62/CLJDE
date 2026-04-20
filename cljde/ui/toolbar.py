"""Main application toolbar for CLJDE.

Builds a single horizontal toolbar with ``QAction`` entries for the
most common commands. Every action is wired to a named slot on the
main window so later phases can replace the slot without touching this
module. Icons are deferred to Phase 8; for now the toolbar is text-only.

Shortcuts are owned by the menu bar, not the toolbar: assigning the
same key sequence to two distinct ``QAction`` instances triggers Qt's
"ambiguous shortcut overload" path and silently suppresses both. The
tooltip here shows the menu's shortcut for discoverability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolBar, QWidget

if TYPE_CHECKING:
    from cljde.main_window import MainWindow


TOOLBAR_OBJECT_NAME = "ClideMainToolBar"

REPL_START_ACTION_NAME = "toolbar_repl_start"
REPL_STOP_ACTION_NAME = "toolbar_repl_stop"
REPL_RESTART_ACTION_NAME = "toolbar_repl_restart"


def build_main_toolbar(window: "MainWindow") -> QToolBar:
    """Construct and return the CLJDE main toolbar attached to ``window``."""
    tb = QToolBar("Main", window)
    tb.setObjectName(TOOLBAR_OBJECT_NAME)
    tb.setMovable(True)
    tb.setFloatable(False)

    _add_file_group(tb, window)
    tb.addSeparator()
    _add_edit_group(tb, window)
    tb.addSeparator()
    _add_repl_group(tb, window)
    tb.addSeparator()
    _add_eval_group(tb, window)

    return tb


def _add_file_group(tb: QToolBar, window: "MainWindow") -> None:
    """Add New / Open / Save actions to the toolbar."""
    tb.addAction(_make_action(tb, "New", "Ctrl+N", window.stub_file_new))
    tb.addAction(_make_action(tb, "Open", "Ctrl+O", window.stub_file_open))
    tb.addAction(_make_action(tb, "Save", "Ctrl+S", window.stub_file_save))


def _add_edit_group(tb: QToolBar, window: "MainWindow") -> None:
    """Add Undo / Redo actions to the toolbar."""
    tb.addAction(_make_action(tb, "Undo", "Ctrl+Z", window.stub_edit_undo))
    tb.addAction(_make_action(tb, "Redo", "Ctrl+Shift+Z", window.stub_edit_redo))


def _add_repl_group(tb: QToolBar, window: "MainWindow") -> None:
    """Add REPL lifecycle actions to the toolbar; Stop/Restart start disabled."""
    start = _make_action(tb, "Start REPL", None, window.stub_repl_start)
    start.setObjectName(REPL_START_ACTION_NAME)
    start.setEnabled(False)
    stop = _make_action(tb, "Stop REPL", None, window.stub_repl_stop)
    stop.setObjectName(REPL_STOP_ACTION_NAME)
    stop.setEnabled(False)
    restart = _make_action(tb, "Restart REPL", None, window.stub_repl_restart)
    restart.setObjectName(REPL_RESTART_ACTION_NAME)
    restart.setEnabled(False)
    tb.addAction(start)
    tb.addAction(stop)
    tb.addAction(restart)


def set_repl_button_states(
    toolbar: QToolBar,
    *,
    can_start: bool,
    can_stop: bool,
    can_restart: bool,
) -> None:
    """Toggle the enable state of the three REPL lifecycle toolbar actions."""
    for name, enabled in (
        (REPL_START_ACTION_NAME, can_start),
        (REPL_STOP_ACTION_NAME, can_stop),
        (REPL_RESTART_ACTION_NAME, can_restart),
    ):
        action = toolbar.findChild(QAction, name)
        if action is not None:
            action.setEnabled(enabled)


def _add_eval_group(tb: QToolBar, window: "MainWindow") -> None:
    """Add evaluation actions to the toolbar."""
    tb.addAction(_make_action(tb, "Eval Form", "Ctrl+Return", window.stub_eval_form))
    tb.addAction(_make_action(
        tb, "Eval Selection", "Ctrl+Shift+Return", window.stub_eval_selection,
    ))
    tb.addAction(_make_action(tb, "Eval File", "Ctrl+Alt+Return", window.stub_eval_file))


def _make_action(
    parent: QWidget,
    text: str,
    shortcut_hint: str | None,
    slot,
) -> QAction:
    """Create a shortcut-free ``QAction`` whose tooltip shows the menu key."""
    action = QAction(text, parent)
    tooltip = f"{text} ({shortcut_hint})" if shortcut_hint else text
    action.setToolTip(tooltip)
    action.triggered.connect(slot)
    return action
