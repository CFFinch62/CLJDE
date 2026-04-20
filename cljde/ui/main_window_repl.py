"""REPL-specific plumbing for :class:`cljde.main_window.MainWindow`.

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

from cljde.editor import form_detector
from cljde.namespace import ns_operations
from cljde.nrepl.client import NreplClient
from cljde.nrepl.session import SessionManager
from cljde.repl.repl_pane import ReplPane
from cljde.ui import toolbar as toolbar_mod
from cljde.ui.connect_dialog import ConnectDialog
from cljde.ui.fuzzy_ns_dialog import FuzzyNsDialog

if TYPE_CHECKING:
    from cljde.main_window import MainWindow

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


# ------------------------------------------------------ process lifecycle

def refresh_repl_ui(window: "MainWindow") -> None:
    """Recompute REPL toolbar button states and crash indicator on the status bar."""
    project = window.file_tree().project()
    is_clojure = project is not None and project.type in ("lein", "deps")
    state = window.process_manager().state()
    running = state in ("starting", "running")
    stopping = state == "stopping"
    can_start = is_clojure and not running and not stopping
    can_stop = running
    can_restart = is_clojure and not stopping
    toolbar_mod.set_repl_button_states(
        window.toolbar(),
        can_start=can_start,
        can_stop=can_stop,
        can_restart=can_restart,
    )
    if state == "crashed":
        window.status_bar().set_repl_status("REPL: crashed", error=True)


def wire_process_manager(window: "MainWindow") -> None:
    """Connect the :class:`ReplProcessManager` signals into the main window."""
    pm = window.process_manager()
    pm.process_state_signal.connect(lambda s: _on_process_state(window, s))
    pm.port_detected_signal.connect(lambda p: auto_connect_after_startup(window, p))
    pm.output_line_signal.connect(lambda line, stream: _on_process_output(window, line, stream))
    pm.error_signal.connect(lambda msg: _on_process_error(window, msg))
    refresh_repl_ui(window)


def start_repl(window: "MainWindow") -> None:
    """REPL > Start — spawn an nREPL for the current project and auto-connect."""
    project = window.file_tree().project()
    if project is None:
        _notice(window, "Open a project first", beep=True)
        return
    if project.type not in ("lein", "deps"):
        _notice(window, "Cannot start REPL for non-Clojure project", beep=True)
        return
    pm = window.process_manager()
    if pm.is_running():
        _notice(window, "REPL already running; use Restart to replace it.")
        return
    window.repl_pane().output_view().append_info(
        f"Starting REPL in {project.root}...",
    )
    pm.start(project, window.settings())


def stop_repl(window: "MainWindow") -> None:
    """REPL > Stop — disconnect the client then terminate the child process."""
    pane = window.repl_pane()
    pm = window.process_manager()
    if pane.endpoint() is not None:
        pane.disconnect()
    if pm.is_running():
        pane.output_view().append_info("Stopping REPL...")
        pm.stop()


def restart_repl(window: "MainWindow") -> None:
    """REPL > Restart — stop the current process then start a fresh one."""
    project = window.file_tree().project()
    if project is None or project.type not in ("lein", "deps"):
        _notice(window, "Cannot restart: no Clojure project open", beep=True)
        return
    pane = window.repl_pane()
    pm = window.process_manager()
    if pane.endpoint() is not None:
        pane.disconnect()
    pane.output_view().append_info("Restarting REPL...")
    pm.restart(project, window.settings())


def auto_connect_after_startup(window: "MainWindow", port: int) -> None:
    """Connect the nREPL client to ``port`` once the spawned process is listening."""
    pane = window.repl_pane()
    pane.output_view().append_info(f"nREPL on port {port}, connecting...")
    pane.connect_to("127.0.0.1", port)


def _on_process_state(window: "MainWindow", state: str) -> None:
    """Recompose the UI on every process-state transition and log crashes."""
    if state == "crashed":
        window.repl_pane().output_view().append_info(
            "REPL process crashed or exited unexpectedly.",
        )
    elif state == "stopped":
        window.repl_pane().output_view().append_info("REPL process stopped.")
    refresh_repl_ui(window)


def _on_process_output(window: "MainWindow", line: str, _stream: str) -> None:
    """Stream a line of REPL-process output into the pane in the info colour."""
    if not line:
        return
    window.repl_pane().output_view().append_info(line)


def _on_process_error(window: "MainWindow", message: str) -> None:
    """Surface a :class:`ReplProcessManager` error to the user."""
    window.repl_pane().output_view().append_info(f"REPL error: {message}")
    window.status_bar().show_transient(message, 4000)


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



# ----------------------------------------------------- namespace operations

def wire_ns_browser(window: "MainWindow") -> None:
    """Connect the :class:`NsBrowser` to the nREPL client and REPL pane."""
    browser = window.ns_browser()
    client = window.repl_pane().client()
    client.session_cloned_signal.connect(lambda _s: browser.refresh())
    window.repl_pane().ns_changed_signal.connect(browser.set_current_ns)
    browser.switch_ns_signal.connect(lambda ns: _switch_via_browser(window, ns))
    browser.reload_ns_signal.connect(lambda ns: _reload_via_browser(window, ns))
    browser.remove_ns_signal.connect(
        lambda ns: _remove_and_refresh(window, ns),
    )


def _switch_via_browser(window: "MainWindow", ns_name: str) -> None:
    """Send ``(in-ns 'NS)`` from a browser double-click with visible feedback."""
    client = window.repl_pane().client()
    if ns_operations.switch_ns(client, ns_name) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info(f"Switching to {ns_name}...")


def _reload_via_browser(window: "MainWindow", ns_name: str) -> None:
    """Send ``(require 'NS :reload)`` from a browser menu with feedback."""
    client = window.repl_pane().client()
    if ns_operations.reload_ns(client, ns_name) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info(f"Reloading {ns_name}...")


def _remove_and_refresh(window: "MainWindow", ns_name: str) -> None:
    """Send ``(remove-ns ...)`` and repopulate the browser afterwards."""
    client = window.repl_pane().client()
    ns_operations.remove_ns(client, ns_name)
    window.ns_browser().refresh()


def reload_current_ns(window: "MainWindow") -> None:
    """Issue ``(require '<file-ns> :reload)`` for the active editor's namespace."""
    ns_name = _current_file_ns(window)
    if ns_name is None:
        _notice(window, "No namespace in current file", beep=True)
        return
    client = window.repl_pane().client()
    if ns_operations.reload_ns(client, ns_name) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info(f"Reloading {ns_name}...")


def switch_to_file_ns(window: "MainWindow") -> None:
    """Switch the REPL to the active editor's file namespace."""
    ns_name = _current_file_ns(window)
    if ns_name is None:
        _notice(window, "No namespace in current file", beep=True)
        return
    client = window.repl_pane().client()
    if ns_operations.switch_ns(client, ns_name) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info(f"Switching to {ns_name}...")


def reload_all_changed(window: "MainWindow") -> None:
    """Invoke ``clojure.tools.namespace.repl/refresh`` in the REPL."""
    client = window.repl_pane().client()
    if ns_operations.reload_all_changed(client) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info("Reloading changed namespaces...")


def goto_namespace(window: "MainWindow") -> None:
    """Prompt for a namespace via fuzzy dialog and switch the REPL to it."""
    browser = window.ns_browser()
    names = browser.all_namespaces()
    if not names:
        _notice(window, "No namespaces loaded", beep=True)
        return
    chosen = FuzzyNsDialog.prompt(names, browser.current_ns(), window)
    if chosen is None:
        return
    client = window.repl_pane().client()
    if ns_operations.switch_ns(client, chosen) is None:
        _notice(window, "REPL not connected", beep=True)
        return
    window.repl_pane().output_view().append_info(f"Switching to {chosen}...")


def _current_file_ns(window: "MainWindow") -> str | None:
    """Return the namespace of the active editor's text, or ``None``."""
    editor = window.editor()
    if editor is None:
        return None
    return form_detector.detect_file_namespace(editor.get_text())
