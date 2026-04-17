"""CLIDE main window: four-zone layout with persistent geometry.

The central widget is a placeholder for the editor tabs. Three
``QDockWidget`` instances host the file tree (left), namespace browser
(right), and REPL pane (bottom). All four zones are ``QLabel``
placeholders for Phase 1 — functional widgets replace them in later
phases without changing this layout.

Menu and toolbar actions are wired to ``stub_*`` methods on this class;
every stub logs ``not implemented: <menu path>`` so clicking through
the UI produces visible activity in the log file.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QWidget,
)

from clide import __version__
from clide.config.settings import Settings
from clide.editor.editor_widget import EditorWidget
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

        self._wire_editor_signals()
        self._restore_geometry()
        log.info("MainWindow initialised.")

    # ------------------------------------------------------------------ layout

    def _build_central(self) -> None:
        """Create the central editor widget (Phase 2: single editor, no tabs)."""
        self._editor = EditorWidget(self._settings, parent=self)
        self._editor.setObjectName("mainEditor")
        self.setCentralWidget(self._editor)

    def _wire_editor_signals(self) -> None:
        """Connect the central editor's signals to the status bar."""
        self._editor.cursor_position_changed_signal.connect(
            self._status_bar.set_cursor_position,
        )
        # Seed the status bar with the editor's starting cursor position.
        self._status_bar.set_cursor_position(1, 1)

    def editor(self) -> EditorWidget:
        """Return the central editor widget."""
        return self._editor

    def _build_docks(self) -> None:
        """Create the left/right/bottom dock widgets with placeholders."""
        self._tree_dock = _dock(
            "File Tree", "fileTreeDock", _placeholder("File Tree", "fileTreePlaceholder"),
        )
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
        """Persist window geometry/state on close, then accept the event."""
        try:
            self._settings.set_window_geometry(self.saveGeometry())
            self._settings.set_window_state(self.saveState())
            self._settings.set("window", "width", self.width())
            self._settings.set("window", "height", self.height())
            self._settings.save()
            log.info("Window geometry saved.")
        except Exception:  # pragma: no cover - defensive
            log.exception("Failed to save window geometry.")
        super().closeEvent(event)

    # -------------------------------------------------------------- public API

    def status_bar(self) -> ClideStatusBar:
        """Return the main window's status bar."""
        return self._status_bar

    def log_not_implemented(self, menu_path: str) -> None:
        """Record that ``menu_path`` has no implementation yet."""
        log.info("not implemented: %s", menu_path)
        self._status_bar.show_transient(f"Not implemented: {menu_path}", 3000)

    # ------------------------------------------------- menu/toolbar stub slots

    def stub_file_new(self) -> None:
        """Stub for File > New."""
        self.log_not_implemented("File | New")

    def stub_file_open(self) -> None:
        """Stub for File > Open File."""
        self.log_not_implemented("File | Open File")

    def stub_file_open_project(self) -> None:
        """Stub for File > Open Project."""
        self.log_not_implemented("File | Open Project")

    def stub_file_save(self) -> None:
        """Stub for File > Save."""
        self.log_not_implemented("File | Save")

    def stub_file_save_as(self) -> None:
        """Stub for File > Save As."""
        self.log_not_implemented("File | Save As")

    def stub_file_recent(self) -> None:
        """Stub for File > Recent Files."""
        self.log_not_implemented("File | Recent Files")

    def stub_file_exit(self) -> None:
        """Close the window (Exit menu item)."""
        log.info("File | Exit -> closing main window.")
        self.close()

    def stub_edit_undo(self) -> None:
        """Stub for Edit > Undo."""
        self.log_not_implemented("Edit | Undo")

    def stub_edit_redo(self) -> None:
        """Stub for Edit > Redo."""
        self.log_not_implemented("Edit | Redo")

    def stub_edit_cut(self) -> None:
        """Stub for Edit > Cut."""
        self.log_not_implemented("Edit | Cut")

    def stub_edit_copy(self) -> None:
        """Stub for Edit > Copy."""
        self.log_not_implemented("Edit | Copy")

    def stub_edit_paste(self) -> None:
        """Stub for Edit > Paste."""
        self.log_not_implemented("Edit | Paste")

    def stub_edit_find(self) -> None:
        """Stub for Edit > Find."""
        self.log_not_implemented("Edit | Find")

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
