"""CLJDE main window: four-zone layout with persistent geometry.

The central widget hosts a :class:`TabManager` of Clojure editors. The
left dock contains a :class:`FileTreeWidget` rooted at the current
project; the right and bottom docks remain placeholders for the
namespace browser and REPL until later phases populate them.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QMenu, QToolBar, QWidget

from cljde import __version__
from cljde.config.settings import Settings
from cljde.editor.editor_widget import EditorWidget
from cljde.files import file_ops
from cljde.files.file_tree import FileTreeWidget
from cljde.files.tab_manager import TabManager
from cljde.namespace.ns_browser import NsBrowser
from cljde.repl.process_manager import ReplProcessManager
from cljde.repl.repl_pane import ReplPane
from cljde.ui import main_window_repl
from cljde.ui.menubar import build_menu_bar
from cljde.ui.status_bar import ClideStatusBar
from cljde.ui.toolbar import build_main_toolbar

log = logging.getLogger(__name__)

DEFAULT_WIDTH = 1400
DEFAULT_HEIGHT = 900
LEFT_DOCK_WIDTH = 240
RIGHT_DOCK_WIDTH = 260
BOTTOM_DOCK_HEIGHT = 240


class MainWindow(QMainWindow):
    """Top-level window hosting the CLJDE four-zone layout."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

        self.setWindowTitle(f"CLJDE {__version__}")
        self.setObjectName("ClideMainWindow")
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )

        self._build_central()
        self._client, self._session_manager, self._repl_pane = main_window_repl.build_repl(self)
        self._process_manager = ReplProcessManager()
        self._build_docks()

        self.setMenuBar(build_menu_bar(self))
        self._toolbar = build_main_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        self._status_bar = ClideStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._status_bar.set_file_info("no file")
        self._status_bar.clear_cursor_position()
        self._status_bar.set_repl_status("REPL: disconnected", connected=False)

        self._wire_signals()
        main_window_repl.wire_process_manager(self)
        self._attach_recent_menu()
        self._restore_geometry()
        file_ops.restore_session(self)
        self._apply_show_hidden_from_settings()
        log.info("MainWindow initialised.")

    # ------------------------------------------------------------------ layout

    def _build_central(self) -> None:
        """Create the central tab manager hosting Clojure editors."""
        self._tabs = TabManager(self._settings, parent=self)
        self._tabs.setObjectName("mainTabs")
        self.setCentralWidget(self._tabs)

    def _wire_signals(self) -> None:
        """Connect tab manager and file tree signals into main-window slots."""
        self._tabs.cursor_position_changed_signal.connect(self._status_bar.set_cursor_position)
        self._tabs.current_file_changed_signal.connect(self._on_current_file_changed)
        self._tabs.editor_notice_signal.connect(lambda msg: self._status_bar.show_transient(msg, 2500))
        self._tree.file_requested_signal.connect(lambda p: file_ops.open_file(self._tabs, p))
        self._client.connection_state_signal.connect(lambda s: main_window_repl.on_connection_state(self, s))
        self._repl_pane.ns_changed_signal.connect(lambda ns: main_window_repl.on_ns_changed(self, ns))
        main_window_repl.wire_ns_browser(self)

    def tab_manager(self) -> TabManager:
        """Return the central tab manager."""
        return self._tabs

    def repl_pane(self) -> ReplPane:
        """Return the docked REPL pane."""
        return self._repl_pane

    def file_tree(self) -> FileTreeWidget:
        """Return the project file tree widget."""
        return self._tree

    def settings(self) -> Settings:
        """Return the live settings instance."""
        return self._settings

    def editor(self) -> EditorWidget | None:
        """Return the active editor, or ``None`` if no tabs are open."""
        return self._tabs.current_editor()

    def process_manager(self) -> ReplProcessManager:
        """Return the :class:`ReplProcessManager` supervising the nREPL process."""
        return self._process_manager

    def ns_browser(self) -> NsBrowser:
        """Return the docked namespace browser widget."""
        return self._ns_browser

    def _build_docks(self) -> None:
        """Create the left/right/bottom dock widgets."""
        self._tree = FileTreeWidget(self)
        self._tree_dock = _dock("File Tree", "fileTreeDock", self._tree)
        self._tree_dock.setMinimumWidth(LEFT_DOCK_WIDTH // 2)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)

        self._ns_browser = NsBrowser(self._client, self)
        self._ns_dock = _dock("Namespaces", "namespacesDock", self._ns_browser)
        self._ns_dock.setMinimumWidth(RIGHT_DOCK_WIDTH // 2)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._ns_dock)

        self._repl_dock = _dock("REPL", "replDock", self._repl_pane)
        self._repl_dock.setMinimumHeight(BOTTOM_DOCK_HEIGHT // 2)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._repl_dock)

        self.resizeDocks(
            [self._tree_dock, self._ns_dock],
            [LEFT_DOCK_WIDTH, RIGHT_DOCK_WIDTH],
            Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [self._repl_dock], [BOTTOM_DOCK_HEIGHT], Qt.Orientation.Vertical,
        )

    # ------------------------------------------------------- geometry persistence

    def _restore_geometry(self) -> None:
        """Restore saved window geometry and dock state, or apply defaults."""
        geometry = self._settings.window_geometry()
        state = self._settings.window_state()
        applied = False
        if not geometry.isEmpty() and self.restoreGeometry(geometry):
            applied = True
        if not state.isEmpty():
            self.restoreState(state)
        if not applied:
            w = int(self._settings.get("window", "width", DEFAULT_WIDTH))
            h = int(self._settings.get("window", "height", DEFAULT_HEIGHT))
            self.resize(w, h)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist session, stop the REPL process, and save geometry on close."""
        try:
            file_ops.save_session(self)
        except Exception:  # pragma: no cover - defensive
            log.exception("Failed to save session.")
        if not self._confirm_close_all_tabs():
            event.ignore()
            return
        if self._process_manager.is_running():
            self._process_manager.stop()
        try:
            self._settings.set_window_geometry(self.saveGeometry())
            self._settings.set_window_state(self.saveState())
            self._settings.set("window", "width", self.width())
            self._settings.set("window", "height", self.height())
            self._settings.save()
            log.info("Window state and session saved.")
        except Exception:  # pragma: no cover - defensive
            log.exception("Failed to save window state.")
        super().closeEvent(event)

    def _confirm_close_all_tabs(self) -> bool:
        """Close each tab in turn; return False if any prompt was cancelled."""
        while self._tabs.count() > 0:
            if not self._tabs.close_current():
                return False
        return True

    # -------------------------------------------------------------- public API

    def status_bar(self) -> ClideStatusBar:
        """Return the main window's status bar."""
        return self._status_bar

    def toolbar(self) -> QToolBar:
        """Return the main application toolbar."""
        return self._toolbar

    def log_not_implemented(self, menu_path: str) -> None:
        """Record that ``menu_path`` has no implementation yet."""
        log.info("not implemented: %s", menu_path)
        self._status_bar.show_transient(f"Not implemented: {menu_path}", 3000)

    def _start_dir(self) -> str:
        """Return a reasonable starting directory for file dialogs."""
        project = self._tree.project()
        if project is not None:
            return str(project.root)
        last = self._settings.get("files", "last_project_path", "") or ""
        return last or str(Path.home())

    def _on_current_file_changed(self, path: object) -> None:
        """Sync status bar and file-tree highlight with the active editor."""
        if isinstance(path, str) and path:
            self._status_bar.set_file_info(path)
            self._tree.highlight_path(path)
        else:
            self._status_bar.set_file_info("no file")
            self._tree.highlight_path(None)

    def _attach_recent_menu(self) -> None:
        """Swap the flat Recent Files action for a dynamically-built submenu."""
        action = self.findChild(QAction, "stub_file_recent")
        if action is None:
            return
        menu = QMenu("Recent Files", self)
        action.setMenu(menu)
        menu.aboutToShow.connect(lambda: file_ops.populate_recent_menu(menu, self._settings, self._tabs))

    def _apply_show_hidden_from_settings(self) -> None:
        """Sync the View > Show Hidden toggle with the file tree."""
        show = bool(self._settings.get("files", "show_hidden", False))
        self._tree.set_show_hidden(show)
        action = self.findChild(QAction, "stub_view_show_hidden")
        if action is not None:
            action.setChecked(show)

    # ------------------------------------------------- menu/toolbar slots

    def stub_file_new(self) -> None:
        """File > New — add an untitled editor tab."""
        file_ops.new_file(self._tabs)

    def stub_file_open(self) -> None:
        """File > Open File — prompt and open in a new tab."""
        file_ops.open_file_dialog(self, self._tabs, self._start_dir())

    def stub_file_open_project(self) -> None:
        """File > Open Project — prompt for a directory and bind it."""
        file_ops.open_project_dialog(self, self)

    def stub_file_save(self) -> None:
        """File > Save — save the active tab (or Save As for untitled)."""
        if not file_ops.save_file(self._tabs):
            editor = self._tabs.current_editor()
            if editor is not None and editor.file_path() is None:
                file_ops.save_file_as(self, self._tabs)

    def stub_file_save_as(self) -> None:
        """File > Save As — prompt for a path and write the active tab."""
        file_ops.save_file_as(self, self._tabs)

    def stub_file_exit(self) -> None:
        """Close the window (Exit menu item)."""
        self.close()

    def _delegate_to_editor(self, method: str, path: str) -> None:
        """Invoke ``method`` on the active editor, logging if none exists."""
        editor = self._tabs.current_editor()
        if editor is None:
            self.log_not_implemented(path)
            return
        getattr(editor, method)()

    def stub_edit_undo(self) -> None:
        """Edit > Undo on the active editor."""
        self._delegate_to_editor("undo", "Edit | Undo")

    def stub_edit_redo(self) -> None:
        """Edit > Redo on the active editor."""
        self._delegate_to_editor("redo", "Edit | Redo")

    def stub_edit_cut(self) -> None:
        """Edit > Cut on the active editor."""
        self._delegate_to_editor("cut", "Edit | Cut")

    def stub_edit_copy(self) -> None:
        """Edit > Copy on the active editor."""
        self._delegate_to_editor("copy", "Edit | Copy")

    def stub_edit_paste(self) -> None:
        """Edit > Paste on the active editor."""
        self._delegate_to_editor("paste", "Edit | Paste")

    def stub_view_show_hidden(self, checked: bool = False) -> None:
        """Toggle display of hidden files in the project tree."""
        self._tree.set_show_hidden(checked)
        self._settings.set("files", "show_hidden", bool(checked))

    def stub_view_toggle_tree(self, checked: bool = True) -> None:
        """Toggle the visibility of the file tree dock."""
        self._tree_dock.setVisible(checked)

    def stub_view_toggle_repl(self, checked: bool = True) -> None:
        """Toggle the visibility of the REPL dock."""
        self._repl_dock.setVisible(checked)

    def stub_view_toggle_namespaces(self, checked: bool = True) -> None:
        """Toggle the visibility of the namespace browser dock."""
        self._ns_dock.setVisible(checked)

    def stub_view_rainbow_parens(self, checked: bool = False) -> None:
        """Toggle rainbow-parens shading on every open editor tab."""
        self._settings.set("editor", "rainbow_parens", bool(checked))
        self._tabs.set_rainbow_parens_all(bool(checked))

    def stub_view_full_screen(self, checked: bool = False) -> None:
        """Toggle full-screen mode on the main window."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def stub_repl_start(self) -> None:
        """REPL > Start — spawn an nREPL for the current project and auto-connect."""
        main_window_repl.start_repl(self)

    def stub_repl_stop(self) -> None:
        """REPL > Stop — disconnect and terminate the nREPL process."""
        main_window_repl.stop_repl(self)

    def stub_repl_restart(self) -> None:
        """REPL > Restart — stop then start a fresh nREPL process."""
        main_window_repl.restart_repl(self)

    def stub_repl_connect(self) -> None:
        """REPL > Connect External — open the connection dialog."""
        main_window_repl.open_connect_dialog(self)

    def stub_repl_disconnect(self) -> None:
        """REPL > Disconnect — close the current nREPL connection."""
        main_window_repl.disconnect(self)

    def stub_eval_form(self) -> None:
        """REPL > Eval Form — evaluate the form under the cursor."""
        main_window_repl.eval_form_at_cursor(self)

    def stub_eval_selection(self) -> None:
        """REPL > Eval Selection — evaluate the active editor's selection."""
        main_window_repl.eval_selection(self)

    def stub_eval_file(self) -> None:
        """REPL > Eval File — load-file the active editor's buffer."""
        main_window_repl.eval_current_file(self)

    def stub_repl_reload_current_ns(self) -> None:
        """REPL > Reload Current NS — require :reload the active file's ns."""
        main_window_repl.reload_current_ns(self)

    def stub_repl_switch_to_file_ns(self) -> None:
        """REPL > Switch to File NS — in-ns to the active file's namespace."""
        main_window_repl.switch_to_file_ns(self)

    def stub_repl_reload_all_changed(self) -> None:
        """REPL > Reload All Changed NS — clojure.tools.namespace/refresh."""
        main_window_repl.reload_all_changed(self)

    def stub_file_goto_namespace(self) -> None:
        """File > Go to Namespace... — fuzzy-select and switch REPL ns."""
        main_window_repl.goto_namespace(self)

    def stub_help_quick_reference(self) -> None:
        """Help > Quick Reference — open the Clojure and CLJDE cheat sheet."""
        from cljde.ui.quick_reference_dialog import QuickReferenceDialog
        QuickReferenceDialog.show_for(self)

    def stub_help_about(self) -> None:
        """Help > About — show version, Python, and Qt runtime info."""
        from cljde.ui.help_dialogs import show_about
        show_about(self)


def _dock(title: str, object_name: str, widget: QWidget) -> QDockWidget:
    """Create a configured dock widget wrapping ``widget``."""
    features = QDockWidget.DockWidgetFeature
    dock = QDockWidget(title)
    dock.setObjectName(object_name)
    dock.setFeatures(features.DockWidgetMovable | features.DockWidgetFloatable | features.DockWidgetClosable)
    dock.setWidget(widget)
    return dock
