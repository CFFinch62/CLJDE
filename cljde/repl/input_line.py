"""Single-expression REPL input widget with history and grow-on-newline.

Enter submits the current buffer as a :attr:`submit_signal`. Shift+Enter
inserts a newline and grows the widget vertically up to a soft cap.
Up/Down cycle through in-memory eval history (capped at
:data:`HISTORY_CAP` entries) when the cursor is on the first/last line.
The widget is styled with :class:`ClojureHighlighter` so user input
reads consistently with the editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QWidget

from cljde.editor.clojure_highlighter import ClojureHighlighter

if TYPE_CHECKING:
    from cljde.config.settings import Settings

HISTORY_CAP = 500
MIN_VISIBLE_LINES = 1
MAX_VISIBLE_LINES = 8


class InputLine(QPlainTextEdit):
    """Expandable REPL prompt with Enter-submit and Up/Down history."""

    submit_signal = pyqtSignal(str)

    def __init__(
        self,
        settings: "Settings | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._history: list[str] = []
        self._history_idx: int | None = None
        self._draft: str = ""

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setObjectName("replInputLine")
        self.setTabChangesFocus(False)
        self._apply_font()

        self._highlighter = ClojureHighlighter(self.document())

        self.textChanged.connect(self._resize_to_content)
        self._resize_to_content()

    # ------------------------------------------------------------ public API

    def history(self) -> list[str]:
        """Return a copy of the in-memory eval history, oldest first."""
        return list(self._history)

    def clear_history(self) -> None:
        """Drop all recorded history entries."""
        self._history.clear()
        self._history_idx = None
        self._draft = ""

    # ---------------------------------------------------- Qt event overrides

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Route Enter/Shift+Enter and first/last-line Up/Down to history."""
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods == Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            if mods == Qt.KeyboardModifier.NoModifier:
                self._submit()
                return
            # Ctrl+Enter and friends are global shortcuts; let them bubble.
            event.ignore()
            return

        if key == Qt.Key.Key_Up and mods == Qt.KeyboardModifier.NoModifier:
            if self._on_first_line() and self._history:
                self._recall_previous()
                return

        if key == Qt.Key.Key_Down and mods == Qt.KeyboardModifier.NoModifier:
            if self._on_last_line() and self._history_idx is not None:
                self._recall_next()
                return

        super().keyPressEvent(event)

    # --------------------------------------------------------- internals

    def _apply_font(self) -> None:
        """Match the editor font so input reads consistently with source."""
        family = "monospace"
        size = 11
        if self._settings is not None:
            family = str(self._settings.get("editor", "font_family", family))
            size = int(self._settings.get("editor", "font_size", size))
        font = QFont(family)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(size)
        self.setFont(font)

    def _submit(self) -> None:
        """Emit :attr:`submit_signal` with the current text and reset."""
        code = self.toPlainText()
        stripped = code.strip()
        if not stripped:
            return
        if not self._history or self._history[-1] != code:
            self._history.append(code)
            if len(self._history) > HISTORY_CAP:
                del self._history[0 : len(self._history) - HISTORY_CAP]
        self._history_idx = None
        self._draft = ""
        self.clear()
        self.submit_signal.emit(code)

    def _on_first_line(self) -> bool:
        """Return True if the cursor sits on the document's first line."""
        return self.textCursor().blockNumber() == 0

    def _on_last_line(self) -> bool:
        """Return True if the cursor sits on the document's last line."""
        return self.textCursor().blockNumber() == self.document().blockCount() - 1

    def _recall_previous(self) -> None:
        """Move one step back into history, preserving the current draft."""
        if self._history_idx is None:
            self._draft = self.toPlainText()
            self._history_idx = len(self._history) - 1
        elif self._history_idx > 0:
            self._history_idx -= 1
        else:
            return
        self._replace_text(self._history[self._history_idx])

    def _recall_next(self) -> None:
        """Move one step forward in history, restoring draft when exhausted."""
        assert self._history_idx is not None  # guarded by the caller
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._replace_text(self._history[self._history_idx])
        else:
            self._history_idx = None
            self._replace_text(self._draft)
            self._draft = ""

    def _replace_text(self, text: str) -> None:
        """Replace the buffer contents and move the cursor to the end."""
        self.blockSignals(True)
        self.setPlainText(text)
        self.blockSignals(False)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        """Grow the widget vertically to fit its content, within bounds."""
        lines = max(MIN_VISIBLE_LINES, min(MAX_VISIBLE_LINES, self.document().blockCount()))
        metrics = self.fontMetrics()
        margins = self.contentsMargins()
        height = lines * metrics.lineSpacing() + margins.top() + margins.bottom() + 8
        self.setFixedHeight(height)
