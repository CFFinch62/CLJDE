"""REPL-specific plumbing for :class:`clide.main_window.MainWindow`.

Extracted to keep ``main_window.py`` under the project's 400-line
ceiling. Every function here takes the main window as its first
argument and uses its public accessors (``settings()``, ``editor()``,
``status_bar()``, ``repl_pane()``) so the module stays a thin glue
layer rather than a second home for Qt state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication

from clide.editor import form_detector
from clide.nrepl.client import NreplClient
from clide.nrepl.session import SessionManager
from clide.repl.repl_pane import ReplPane
from clide.ui.connect_dialog import ConnectDialog

if TYPE_CHECKING:
    from clide.main_window import MainWindow

log = logging.getLogger(__name__)


def build_repl(window: "MainWindow") -> tuple[NreplClient, SessionManager, ReplPane]:
    """Construct the nREPL client, session manager, and :class:`ReplPane`."""
    client = NreplClient(window)
    sessions = SessionManager()
    pane = ReplPane(client, sessions, window.settings(), window)
    return client, sessions, pane


def on_connection_state(window: "MainWindow", state: str) -> None:
    """Update the main-window status bar on each state transition."""
    bar = window.status_bar()
    if state == "connected":
        _write_connected_status(window)
    elif state == "connecting":
        bar.set_repl_status("REPL: connecting...", connected=False)
    elif state == "error":
        bar.set_repl_status("REPL: error", connected=False)
    else:
        bar.set_repl_status("REPL: disconnected", connected=False)


def on_ns_changed(window: "MainWindow", _ns: str) -> None:
    """Rewrite the status bar when the REPL's tracked namespace changes."""
    if window.repl_pane().endpoint() is None:
        return
    _write_connected_status(window)


def _write_connected_status(window: "MainWindow") -> None:
    """Render the ``REPL: connected …`` status-bar line."""
    pane = window.repl_pane()
    endpoint = pane.endpoint()
    suffix = f" :{endpoint[1]}" if endpoint else ""
    window.status_bar().set_repl_status(
        f"REPL: connected{suffix} | ns: {pane.current_ns()}", connected=True,
    )


def eval_form_at_cursor(window: "MainWindow") -> None:
    """Evaluate the innermost balanced form containing the editor cursor."""
    editor = window.editor()
    if editor is None:
        _notice(window, "No active editor", beep=True)
        return
    text = editor.get_text()
    pos = editor.textCursor().position()
    bounds = form_detector.form_at(text, pos)
    if bounds is None:
        _notice(window, "No form at cursor", beep=True)
        return
    start, end = bounds
    code = text[start:end]
    line, column = _line_column(text, start)
    ns = form_detector.detect_file_namespace(text) or window.repl_pane().current_ns()
    window.repl_pane().eval(
        code, ns=ns, file=editor.file_path(), line=line, column=column,
    )


def eval_selection(window: "MainWindow") -> None:
    """Evaluate the current selection in the active editor."""
    editor = window.editor()
    if editor is None:
        _notice(window, "No active editor", beep=True)
        return
    cursor = editor.textCursor()
    if not cursor.hasSelection():
        _notice(window, "No selection", beep=True)
        return
    text = editor.get_text()
    start = cursor.selectionStart()
    end = cursor.selectionEnd()
    code = text[start:end]
    line, column = _line_column(text, start)
    ns = form_detector.detect_file_namespace(text) or window.repl_pane().current_ns()
    window.repl_pane().eval(
        code, ns=ns, file=editor.file_path(), line=line, column=column,
    )


def eval_current_file(window: "MainWindow") -> None:
    """Send the active editor's buffer as a ``load-file`` request."""
    editor = window.editor()
    if editor is None:
        _notice(window, "No active editor", beep=True)
        return
    text = editor.get_text()
    path = editor.file_path() or ""
    if path:
        file_name = Path(path).name
        file_path = path
    else:
        file_name = "untitled.clj"
        file_path = "<untitled>"
    pane = window.repl_pane()
    pane.load_file(text, file_name, file_path)
    file_ns = form_detector.detect_file_namespace(text)
    if file_ns:
        pane.eval(f"(in-ns '{file_ns})")


def open_connect_dialog(window: "MainWindow") -> None:
    """Prompt for a host/port and ask the REPL pane to connect."""
    result = ConnectDialog.prompt(window.settings(), window)
    if result is None:
        return
    host, port = result
    window.repl_pane().connect_to(host, port)


def disconnect(window: "MainWindow") -> None:
    """Disconnect the REPL pane from its nREPL endpoint."""
    window.repl_pane().disconnect()


def _line_column(text: str, pos: int) -> tuple[int, int]:
    """Return the 1-based (line, column) for ``pos`` within ``text``."""
    if pos <= 0:
        return 1, 1
    head = text[:pos]
    line = head.count("\n") + 1
    last_nl = head.rfind("\n")
    column = pos - last_nl if last_nl >= 0 else pos + 1
    return line, column


def _notice(window: "MainWindow", message: str, *, beep: bool = False) -> None:
    """Post a user-visible notice to both the status bar and the REPL pane."""
    if beep:
        QApplication.beep()
    window.status_bar().show_transient(message, 2000)
    window.repl_pane().output_view().append_info(message)
