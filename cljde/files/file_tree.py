"""Project file tree widget.

Wraps a :class:`QFileSystemModel` in a :class:`QTreeView` under a small
header showing the current project name. Double-clicking a file emits
:attr:`file_requested_signal`. A context menu exposes the usual new /
rename / delete / reveal operations.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QDir, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFileSystemModel
from PyQt6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cljde.config.theme import DEFAULT_PALETTE
from cljde.files.project import Project

log = logging.getLogger(__name__)


class FileTreeWidget(QWidget):
    """Project-scoped file tree with context menu and active-file highlighting."""

    file_requested_signal = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._show_hidden = False

        self._title = QLabel("No Project")
        self._title.setObjectName("fileTreeTitle")
        self._title.setStyleSheet(
            f"color: {DEFAULT_PALETTE.amber_primary};"
            " font-weight: bold; padding: 4px 6px;"
        )

        self._model = QFileSystemModel(self)
        self._model.setReadOnly(False)
        self._apply_filter_flags()

        self._view = QTreeView(self)
        self._view.setModel(self._model)
        self._view.setHeaderHidden(True)
        self._view.setAnimated(False)
        self._view.setIndentation(14)
        self._view.setSortingEnabled(True)
        self._view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for col in range(1, self._model.columnCount()):
            self._view.hideColumn(col)
        self._view.doubleClicked.connect(self._on_double_clicked)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._title)
        layout.addWidget(self._view)

    # ---------------------------------------------------------- public API

    def set_project(self, project: Project | None) -> None:
        """Bind the tree to ``project`` (or clear it if ``None``)."""
        self._project = project
        if project is None:
            self._title.setText("No Project")
            self._view.setRootIndex(QModelIndex())
            return
        self._title.setText(project.name)
        root = str(project.root)
        self._model.setRootPath(root)
        self._view.setRootIndex(self._model.index(root))

    def project(self) -> Project | None:
        """Return the currently bound project (or ``None``)."""
        return self._project

    def set_show_hidden(self, show: bool) -> None:
        """Toggle visibility of dotfiles and hidden entries."""
        self._show_hidden = bool(show)
        self._apply_filter_flags()

    def highlight_path(self, path: str | None) -> None:
        """Select the tree row matching ``path`` if it's under the root."""
        if not path:
            self._view.clearSelection()
            return
        index = self._model.index(path)
        if index.isValid():
            self._view.setCurrentIndex(index)
            self._view.scrollTo(index)

    # ----------------------------------------------------- internal helpers

    def _apply_filter_flags(self) -> None:
        """Rebuild the QDir filter flags from current show-hidden state."""
        flags = (
            QDir.Filter.AllDirs
            | QDir.Filter.Files
            | QDir.Filter.NoDotAndDotDot
        )
        if self._show_hidden:
            flags |= QDir.Filter.Hidden
        self._model.setFilter(flags)

    def _selected_path(self) -> Path | None:
        """Return the filesystem path of the current selection, or None."""
        index = self._view.currentIndex()
        if not index.isValid():
            return None
        return Path(self._model.filePath(index))

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Emit ``file_requested_signal`` for file (not directory) clicks."""
        if not index.isValid() or self._model.isDir(index):
            return
        path = self._model.filePath(index)
        self.file_requested_signal.emit(path)

    def _on_context_menu(self, pos) -> None:
        """Pop up the context menu for the row under ``pos``."""
        menu = QMenu(self)
        new_file = QAction("New File", menu)
        new_dir = QAction("New Directory", menu)
        rename = QAction("Rename", menu)
        delete = QAction("Delete", menu)
        reveal = QAction("Reveal in File Manager", menu)
        new_file.triggered.connect(self._action_new_file)
        new_dir.triggered.connect(self._action_new_dir)
        rename.triggered.connect(self._action_rename)
        delete.triggered.connect(self._action_delete)
        reveal.triggered.connect(self._action_reveal)
        for action in (new_file, new_dir, rename, delete):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(reveal)
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _target_directory(self) -> Path | None:
        """Return the directory to act on: selected dir or its parent."""
        path = self._selected_path()
        if path is None:
            return Path(self._project.root) if self._project else None
        return path if path.is_dir() else path.parent

    def _action_new_file(self) -> None:
        """Create a new empty file under the selected directory."""
        target = self._target_directory()
        if target is None:
            return
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if not ok or not name.strip():
            return
        new_path = target / name.strip()
        try:
            new_path.touch(exist_ok=False)
        except OSError as exc:
            QMessageBox.warning(self, "New File", f"Could not create file:\n{exc}")
            return
        self.file_requested_signal.emit(str(new_path))

    def _action_new_dir(self) -> None:
        """Create a new directory under the selected directory."""
        target = self._target_directory()
        if target is None:
            return
        name, ok = QInputDialog.getText(self, "New Directory", "Directory name:")
        if not ok or not name.strip():
            return
        try:
            (target / name.strip()).mkdir(exist_ok=False)
        except OSError as exc:
            QMessageBox.warning(self, "New Directory", f"Could not create directory:\n{exc}")

    def _action_rename(self) -> None:
        """Rename the currently selected file or directory."""
        path = self._selected_path()
        if path is None:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=path.name,
        )
        if not ok or not new_name.strip() or new_name.strip() == path.name:
            return
        try:
            path.rename(path.with_name(new_name.strip()))
        except OSError as exc:
            QMessageBox.warning(self, "Rename", f"Could not rename:\n{exc}")

    def _action_delete(self) -> None:
        """Delete the selected file or (recursively) directory after prompting."""
        path = self._selected_path()
        if path is None:
            return
        prompt = f"Delete {path.name}?"
        if path.is_dir():
            prompt = f"Delete directory {path.name} and all its contents?"
        if QMessageBox.question(self, "Delete", prompt) != QMessageBox.StandardButton.Yes:
            return
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Delete", f"Could not delete:\n{exc}")

    def _action_reveal(self) -> None:
        """Open the selected path's directory in the system file manager."""
        path = self._selected_path()
        if path is None and self._project is not None:
            path = Path(self._project.root)
        if path is None:
            return
        target = path if path.is_dir() else path.parent
        _reveal_in_file_manager(target)


def _reveal_in_file_manager(path: Path) -> None:
    """Launch the OS file manager on ``path`` (best-effort, non-blocking)."""
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(path)])
    except OSError as exc:
        log.warning("Could not reveal %s: %s", path, exc)
