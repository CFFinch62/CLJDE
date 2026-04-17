"""Functional module for file and project operations.

These functions take a :class:`TabManager` and/or :class:`MainWindow`
and mutate their state. Keeping the logic out of the widget classes
themselves lets menu actions, toolbar buttons, and session restore
share a single surface without introducing a new orchestrator class.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QMenu, QWidget

from clide.config.settings import Settings
from clide.files.project import detect_project

if TYPE_CHECKING:
    from clide.files.tab_manager import TabManager
    from clide.main_window import MainWindow

log = logging.getLogger(__name__)

CLOJURE_FILTER = "Clojure (*.clj *.cljs *.cljc *.edn);;All files (*)"


# -------------------------------------------------------- file operations

def new_file(tab_mgr: "TabManager") -> None:
    """Create a new untitled editor tab."""
    tab_mgr.new_untitled()


def open_file_dialog(parent: QWidget, tab_mgr: "TabManager", start_dir: str) -> None:
    """Prompt for a file path and open it via :func:`open_file`."""
    path, _ = QFileDialog.getOpenFileName(
        parent, "Open File", start_dir, CLOJURE_FILTER,
    )
    if path:
        open_file(tab_mgr, path)


def open_file(tab_mgr: "TabManager", path: str) -> None:
    """Open ``path`` in the tab manager and add to recent files."""
    resolved = str(Path(path).resolve())
    tab_mgr.open_file(resolved)
    settings = tab_mgr.settings()
    if settings is not None:
        _add_recent(settings, resolved)
        settings.save()


def save_file(tab_mgr: "TabManager") -> bool:
    """Save the active tab, falling back to Save-As if it has no path."""
    editor = tab_mgr.current_editor()
    if editor is None:
        return False
    if editor.file_path() is None:
        # Cannot silently save an untitled tab; caller should route to save-as.
        return False
    return tab_mgr.save_current()


def save_file_as(parent: QWidget, tab_mgr: "TabManager") -> bool:
    """Prompt for a destination path and write the active tab to it."""
    editor = tab_mgr.current_editor()
    if editor is None:
        return False
    start = editor.file_path() or ""
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save File As", start, CLOJURE_FILTER,
    )
    if not path:
        return False
    ok = tab_mgr.save_current_as(path)
    if ok:
        settings = tab_mgr.settings()
        if settings is not None:
            _add_recent(settings, str(Path(path).resolve()))
            settings.save()
    return ok


def close_file(tab_mgr: "TabManager") -> bool:
    """Close the active tab (prompting for unsaved changes)."""
    return tab_mgr.close_current()


# ------------------------------------------------------ project operations

def open_project_dialog(parent: QWidget, main_window: "MainWindow") -> None:
    """Prompt for a project directory and open it."""
    start = main_window.settings().get("files", "last_project_path", "") or str(Path.home())
    path = QFileDialog.getExistingDirectory(parent, "Open Project", start)
    if path:
        open_project(main_window, path)


def open_project(main_window: "MainWindow", path: str) -> None:
    """Detect and bind a project rooted at (or above) ``path``."""
    project = detect_project(Path(path))
    if project is None:
        log.info("No project markers found at %s; using directory as-is.", path)
        from clide.files.project import Project
        root = Path(path).resolve()
        project = Project(root=root, type="other", name=root.name)
    main_window.file_tree().set_project(project)
    settings = main_window.settings()
    settings.set("files", "last_project_path", str(project.root))
    settings.save()
    main_window.status_bar().show_transient(
        f"Project: {project.name} ({project.type})", 4000,
    )
    log.info("Opened project %s (%s) at %s", project.name, project.type, project.root)


# --------------------------------------------------------- recent files

def _add_recent(settings: Settings, path: str) -> None:
    """Push ``path`` to the front of the recent-files list, deduped."""
    recent = list(settings.get("files", "recent_files", []) or [])
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    limit = int(settings.get("files", "max_recent", 10))
    settings.set("files", "recent_files", recent[:limit])


def populate_recent_menu(
    menu: QMenu,
    settings: Settings,
    tab_mgr: "TabManager",
) -> None:
    """Rebuild ``menu`` with an action per recent file and a Clear entry."""
    menu.clear()
    recent = list(settings.get("files", "recent_files", []) or [])
    if not recent:
        empty = QAction("(no recent files)", menu)
        empty.setEnabled(False)
        menu.addAction(empty)
        return
    for entry in recent:
        action = QAction(entry, menu)
        action.triggered.connect(lambda _checked=False, p=entry: open_file(tab_mgr, p))
        menu.addAction(action)
    menu.addSeparator()
    clear = QAction("Clear Recent Files", menu)
    clear.triggered.connect(lambda: _clear_recent(settings))
    menu.addAction(clear)


def _clear_recent(settings: Settings) -> None:
    """Empty the recent-files list and persist."""
    settings.set("files", "recent_files", [])
    settings.save()


# --------------------------------------------------------- session state

def save_session(main_window: "MainWindow") -> None:
    """Persist open tabs, active tab index, and last project path."""
    settings = main_window.settings()
    tab_mgr = main_window.tab_manager()
    project = main_window.file_tree().project()
    if project is not None:
        settings.set("files", "last_project_path", str(project.root))
    settings.set("files", "open_tabs", tab_mgr.open_tabs_state())
    settings.set("files", "current_tab_index", max(0, tab_mgr.currentIndex()))
    settings.save()


def restore_session(main_window: "MainWindow") -> None:
    """Reopen last project and previously-open tabs with cursor positions."""
    settings = main_window.settings()
    last_project = settings.get("files", "last_project_path", "")
    if last_project and Path(last_project).is_dir():
        try:
            open_project(main_window, last_project)
        except OSError:
            log.exception("Failed to restore project %s", last_project)
    tab_mgr = main_window.tab_manager()
    open_tabs = list(settings.get("files", "open_tabs", []) or [])
    for entry in open_tabs:
        path = entry.get("path")
        if not path or not Path(path).is_file():
            continue
        tab_mgr.open_file(path)
        editor = tab_mgr.current_editor()
        if editor is not None:
            editor.set_cursor_line_column(
                int(entry.get("line", 1)), int(entry.get("column", 1)),
            )
    index = int(settings.get("files", "current_tab_index", 0))
    if 0 <= index < tab_mgr.count():
        tab_mgr.setCurrentIndex(index)

