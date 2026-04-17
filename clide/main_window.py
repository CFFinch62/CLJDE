"""CLIDE main window: four-zone layout with persistent geometry.

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
from PyQt6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QMenu,
    QWidget,
)

from clide import __version__
from clide.config.settings import Settings
from clide.editor.editor_widget import EditorWidget
from clide.files import file_ops
from clide.files.file_tree import FileTreeWidget
from clide.files.tab_manager import TabManager
from clide.ui.menubar import build_menu_bar
from clide.ui.status_bar import ClideStatusBar
from clide.ui.toolbar import build_main_toolbar

log = logging.getLogger(__name__)

DEFAULT_WIDTH = 1400
DEFAULT_HEIGHT = 900
LEFT_DOCK_WIDTH = 240
RIGHT_DOCK_WIDTH = 260
BOTTOM_DOCK_HEIGHT = 240


class MainWindow(QMainWindow):
    """Top-level window hosting the CLIDE four-zone layout."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

        self.setWindowTitle(f"CLIDE {__version__}")
        self.setObjectName("ClideMainWindow")
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )

        self._build_central()
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
        self._tabs.cursor_position_changed_signal.connect(
            self._status_bar.set_cursor_position,
        )
        self._tabs.current_file_changed_signal.connect(self._on_current_file_changed)
        self._tree.file_requested_signal.connect(
            lambda p: file_ops.open_file(self._tabs, p),
        )

    def tab_manager(self) -> TabManager:
        """Return the central tab manager."""
        return self._tabs

    def file_tree(self) -> FileTreeWidget:
        """Return the project file tree widget."""
        return self._tree

    def settings(self) -> Settings:
        """Return the live settings instance."""
        return self._settings

    def editor(self) -> EditorWidget | None:
        """Return the active editor, or ``None`` if no tabs are open."""
        return self._tabs.current_editor()

    def _build_docks(self) -> None:
        """Create the left/right/bottom dock widgets."""
        self._tree = FileTreeWidget(self)
        self._tree_dock = _dock("File Tree", "fileTreeDock", self._tree)
        self._tree_dock.setMinimumWidth(LEFT_DOCK_WIDTH // 2)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)

        self._ns_dock = _dock(
            "Namespaces", "namespacesDock", _placeholder("Namespaces", "nsPlaceholder"),
        )
        self._ns_dock.setMinimumWidth(RIGHT_DOCK_WIDTH // 2)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._ns_dock)

        self._repl_dock = _dock(
            "REPL", "replDock", _placeholder("REPL", "replPlaceholder"),
        )
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
        """Persist session first, then prompt for unsaved tabs and save geometry."""
        try:
            file_ops.save_session(self)
        except Exception:  # pragma: no cover - defensive
            log.exception("Failed to save session.")
        if not self._confirm_close_all_tabs():
            event.ignore()
            return
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
        menu.aboutToShow.connect(
            lambda: file_ops.populate_recent_menu(menu, self._settings, self._tabs),
        )

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

    def stub_file_recent(self) -> None:
        """File > Recent Files — no-op; the submenu handles activation."""
        return

    def stub_file_exit(self) -> None:
        """Close the window (Exit menu item)."""
        log.info("File | Exit -> closing main window.")
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

    def stub_edit_find(self) -> None:
        """Edit > Find — placeholder until a find dialog ships."""
        self.log_not_implemented("Edit | Find")

    def stub_view_show_hidden(self, checked: bool = False) -> None:
        """Toggle display of hidden files in the project tree."""
        self._tree.set_show_hidden(checked)
        self._settings.set("files", "show_hidden", bool(checked))
        log.info("View | Show Hidden Files -> %s", checked)

    def stub_view_toggle_tree(self, checked: bool = True) -> None:
        """Toggle the visibility of the file tree dock."""
        self._tree_dock.setVisible(checked)
        log.info("View | Toggle File Tree -> %s", checked)

    def stub_view_toggle_repl(self, checked: bool = True) -> None:
        """Toggle the visibility of the REPL dock."""
        self._repl_dock.setVisible(checked)
        log.info("View | Toggle REPL -> %s", checked)

    def stub_view_toggle_namespaces(self, checked: bool = True) -> None:
        """Toggle the visibility of the namespace browser dock."""
        self._ns_dock.setVisible(checked)
        log.info("View | Toggle Namespaces -> %s", checked)

    def stub_view_rainbow_parens(self, checked: bool = False) -> None:
        """Stub for View > Rainbow Parens (persisted to settings)."""
        self._settings.set("editor", "rainbow_parens", bool(checked))
        self.log_not_implemented(f"View | Rainbow Parens ({checked})")

    def stub_view_full_screen(self, checked: bool = False) -> None:
        """Toggle full-screen mode on the main window."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
        log.info("View | Full Screen -> %s", checked)

    def stub_repl_start(self) -> None:
        """Stub for REPL > Start."""
        self.log_not_implemented("REPL | Start")

    def stub_repl_stop(self) -> None:
        """Stub for REPL > Stop."""
        self.log_not_implemented("REPL | Stop")

    def stub_repl_restart(self) -> None:
        """Stub for REPL > Restart."""
        self.log_not_implemented("REPL | Restart")

    def stub_repl_connect(self) -> None:
        """Stub for REPL > Connect External."""
        self.log_not_implemented("REPL | Connect External")

    def stub_eval_form(self) -> None:
        """Stub for REPL > Eval Form."""
        self.log_not_implemented("REPL | Eval Form")

    def stub_eval_selection(self) -> None:
        """Stub for REPL > Eval Selection."""
        self.log_not_implemented("REPL | Eval Selection")

    def stub_eval_file(self) -> None:
        """Stub for REPL > Eval File."""
        self.log_not_implemented("REPL | Eval File")

    def stub_repl_reload_ns(self) -> None:
        """Stub for REPL > Reload Namespace."""
        self.log_not_implemented("REPL | Reload Namespace")

    def stub_repl_switch_ns(self) -> None:
        """Stub for REPL > Switch Namespace."""
        self.log_not_implemented("REPL | Switch Namespace")

    def stub_help_about(self) -> None:
        """Stub for Help > About."""
        self.log_not_implemented("Help | About CLIDE")

    def stub_help_shortcuts(self) -> None:
        """Stub for Help > Shortcuts."""
        self.log_not_implemented("Help | Shortcuts")

    def stub_help_report_issue(self) -> None:
        """Stub for Help > Report Issue."""
        self.log_not_implemented("Help | Report Issue")


def _placeholder(label: str, object_name: str = "") -> QLabel:
    """Create a centred placeholder label used as a panel stand-in."""
    lbl = QLabel(label)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setObjectName(object_name or f"placeholder_{label}")
    lbl.setStyleSheet("font-size: 14pt; color: #a0a0a0;")
    lbl.setMinimumSize(120, 80)
    return lbl


def _dock(title: str, object_name: str, widget: QWidget) -> QDockWidget:
    """Create a configured dock widget wrapping ``widget``."""
    dock = QDockWidget(title)
    dock.setObjectName(object_name)
    dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    dock.setWidget(widget)
    return dock
