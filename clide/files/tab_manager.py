"""Multi-tab editor container for CLIDE.

Wraps a collection of :class:`EditorWidget` instances in a
:class:`PyQt6.QtWidgets.QTabWidget`, tracks per-editor file paths and
modification state, and re-emits the active editor's cursor position so
the main window's status bar can stay in sync across tab switches.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QMessageBox, QTabWidget, QWidget

from clide.editor.editor_widget import EditorWidget

if TYPE_CHECKING:
    from clide.config.settings import Settings

log = logging.getLogger(__name__)


class TabManager(QTabWidget):
    """Tab-based host for multiple ``EditorWidget`` instances."""

    current_file_changed_signal = pyqtSignal(object)   # str | None
    file_modified_signal = pyqtSignal(str, bool)
    cursor_position_changed_signal = pyqtSignal(int, int)
    editor_notice_signal = pyqtSignal(str)

    def __init__(
        self,
        settings: "Settings | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._active_cursor_editor: EditorWidget | None = None

        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self._on_tab_close_requested)
        self.currentChanged.connect(self._on_current_changed)

        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=self._cycle_next)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=self._cycle_prev)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self.close_current)

    # ---------------------------------------------------------- public API

    def settings(self) -> "Settings | None":
        """Return the settings instance this manager was built with."""
        return self._settings

    def open_file(self, path: str) -> None:
        """Open ``path`` in a new tab (or switch to it if already open)."""
        resolved = str(Path(path).resolve())
        existing = self._find_tab_by_path(resolved)
        if existing is not None:
            self.setCurrentIndex(existing)
            return
        try:
            text = Path(resolved).read_text(encoding="utf-8")
        except OSError as exc:
            log.error("Failed to read %s: %s", resolved, exc)
            QMessageBox.warning(self, "Open File", f"Could not open file:\n{exc}")
            return
        editor = self._new_editor(file_path=resolved)
        editor.set_text(text)
        editor.document().setModified(False)
        index = self.addTab(editor, Path(resolved).name)
        self.setTabToolTip(index, resolved)
        self.setCurrentIndex(index)
        log.info("Opened %s", resolved)

    def new_untitled(self) -> EditorWidget:
        """Create and focus a new untitled editor tab."""
        editor = self._new_editor(file_path=None)
        index = self.addTab(editor, "untitled")
        self.setCurrentIndex(index)
        return editor

    def close_file(self, path: str) -> bool:
        """Close the tab for ``path``; returns False if user cancelled."""
        index = self._find_tab_by_path(str(Path(path).resolve()))
        if index is None:
            return True
        return self._close_tab(index)

    def close_current(self) -> bool:
        """Close the currently active tab; returns False if user cancelled."""
        index = self.currentIndex()
        if index < 0:
            return True
        return self._close_tab(index)

    def save_current(self) -> bool:
        """Write the active editor to its file path; False if no path set."""
        editor = self.current_editor()
        if editor is None or editor.file_path() is None:
            return False
        return self._write_editor(editor, editor.file_path())

    def save_current_as(self, path: str) -> bool:
        """Write the active editor to ``path`` and rebind its path."""
        editor = self.current_editor()
        if editor is None:
            return False
        resolved = str(Path(path).resolve())
        if not self._write_editor(editor, resolved):
            return False
        editor.set_file_path(resolved)
        index = self.indexOf(editor)
        self.setTabText(index, Path(resolved).name)
        self.setTabToolTip(index, resolved)
        self.current_file_changed_signal.emit(resolved)
        return True

    def current_editor(self) -> EditorWidget | None:
        """Return the active ``EditorWidget`` or None if no tabs are open."""
        widget = self.currentWidget()
        return widget if isinstance(widget, EditorWidget) else None

    def current_file_path(self) -> str | None:
        """Return the active editor's file path, or None."""
        editor = self.current_editor()
        return editor.file_path() if editor is not None else None

    def modified_files(self) -> list[str]:
        """Return paths of all modified tabs (untitled tabs excluded)."""
        out: list[str] = []
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, EditorWidget) and editor.document().isModified():
                path = editor.file_path()
                if path:
                    out.append(path)
        return out

    def set_rainbow_parens_all(self, enabled: bool) -> None:
        """Toggle rainbow-parens shading on every open editor tab."""
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, EditorWidget):
                editor.set_rainbow_parens(enabled)

    def open_tabs_state(self) -> list[dict]:
        """Return a serialisable snapshot of open (saved) tabs for session restore."""
        state: list[dict] = []
        for i in range(self.count()):
            editor = self.widget(i)
            if not isinstance(editor, EditorWidget):
                continue
            path = editor.file_path()
            if not path:
                continue
            line, col = editor.cursor_line_column()
            state.append({"path": path, "line": line, "column": col})
        return state


    # ----------------------------------------------------- internal helpers

    def _new_editor(self, file_path: str | None) -> EditorWidget:
        """Construct an ``EditorWidget`` wired to this manager's signals."""
        editor = EditorWidget(self._settings, parent=self)
        editor.set_file_path(file_path)
        editor.document().modificationChanged.connect(
            lambda modified, e=editor: self._on_modification_changed(e, modified),
        )
        editor.notice_signal.connect(self.editor_notice_signal)
        return editor

    def _write_editor(self, editor: EditorWidget, path: str) -> bool:
        """Write ``editor`` contents to ``path``; show a dialog on failure."""
        try:
            Path(path).write_text(editor.get_text(), encoding="utf-8")
        except OSError as exc:
            log.error("Failed to write %s: %s", path, exc)
            QMessageBox.warning(self, "Save File", f"Could not save file:\n{exc}")
            return False
        editor.document().setModified(False)
        log.info("Saved %s", path)
        return True

    def _close_tab(self, index: int) -> bool:
        """Close the tab at ``index`` with a save prompt if dirty."""
        editor = self.widget(index)
        if isinstance(editor, EditorWidget) and editor.document().isModified():
            choice = self._prompt_save(editor)
            if choice == QMessageBox.StandardButton.Cancel:
                return False
            if choice == QMessageBox.StandardButton.Save:
                if editor.file_path() is None:
                    return False
                if not self._write_editor(editor, editor.file_path()):
                    return False
        self.removeTab(index)
        editor.deleteLater()
        return True

    def _prompt_save(self, editor: EditorWidget) -> QMessageBox.StandardButton:
        """Show a Save/Discard/Cancel prompt for a modified editor."""
        name = Path(editor.file_path()).name if editor.file_path() else "untitled"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved Changes")
        box.setText(f"Save changes to {name} before closing?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def _find_tab_by_path(self, resolved: str) -> int | None:
        """Return the index of the tab matching ``resolved``, or None."""
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, EditorWidget) and editor.file_path() == resolved:
                return i
        return None

    def _on_tab_close_requested(self, index: int) -> None:
        """Slot for the tab widget's close button."""
        self._close_tab(index)

    def _on_current_changed(self, index: int) -> None:
        """Rewire cursor-position forwarding and emit file-change notice."""
        if self._active_cursor_editor is not None:
            try:
                self._active_cursor_editor.cursor_position_changed_signal.disconnect(
                    self.cursor_position_changed_signal,
                )
            except (TypeError, RuntimeError):
                pass
            self._active_cursor_editor = None
        editor = self.widget(index) if index >= 0 else None
        if isinstance(editor, EditorWidget):
            editor.cursor_position_changed_signal.connect(
                self.cursor_position_changed_signal,
            )
            self._active_cursor_editor = editor
            line, col = editor.cursor_line_column()
            self.cursor_position_changed_signal.emit(line, col)
            self.current_file_changed_signal.emit(editor.file_path())
        else:
            self.current_file_changed_signal.emit(None)

    def _on_modification_changed(self, editor: EditorWidget, modified: bool) -> None:
        """Update the tab label's '*' marker and re-emit to listeners."""
        index = self.indexOf(editor)
        if index < 0:
            return
        name = Path(editor.file_path()).name if editor.file_path() else "untitled"
        self.setTabText(index, f"*{name}" if modified else name)
        path = editor.file_path()
        if path:
            self.file_modified_signal.emit(path, modified)

    def _cycle_next(self) -> None:
        """Activate the next tab (wrapping to the first)."""
        if self.count() == 0:
            return
        self.setCurrentIndex((self.currentIndex() + 1) % self.count())

    def _cycle_prev(self) -> None:
        """Activate the previous tab (wrapping to the last)."""
        if self.count() == 0:
            return
        self.setCurrentIndex((self.currentIndex() - 1) % self.count())
