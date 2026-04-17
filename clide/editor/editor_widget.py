"""CLIDE source-editor widget.

Extends :class:`PyQt6.QtWidgets.QPlainTextEdit` with:
  * a line-number gutter (painted via :class:`LineNumberArea`),
  * a current-line background highlight,
  * paren-match highlighting via :mod:`clide.editor.paren_matcher`,
  * Clojure syntax highlighting via :class:`ClojureHighlighter`,
  * Tab/Shift-Tab converted to ``tab_width`` spaces (default 2),
  * ``cursor_position_changed_signal(line, column)`` emitted on every
    cursor move, intended for wiring to the main status bar.

The widget accepts an optional :class:`Settings` instance; when
provided, font family/size and tab width are read from the
``editor`` section so user preferences take effect on construction.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from clide.config.settings import Settings
from clide.config.theme import DEFAULT_PALETTE
from clide.editor import paren_matcher
from clide.editor.clojure_highlighter import ClojureHighlighter
from clide.editor.line_numbers import LineNumberArea

DEFAULT_FONT_FAMILY = "monospace"
DEFAULT_FONT_SIZE = 11
DEFAULT_TAB_WIDTH = 2
GUTTER_PADDING_PX = 12


class EditorWidget(QPlainTextEdit):
    """Clojure source editor with line numbers, paren match, and highlighting."""

    cursor_position_changed_signal = pyqtSignal(int, int)

    def __init__(
        self,
        settings: Settings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._line_number_area = LineNumberArea(self)
        self._highlighter = ClojureHighlighter(self.document())

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFrameStyle(0)

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._on_update_request)
        self.cursorPositionChanged.connect(self._emit_cursor_position)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self.textChanged.connect(self._refresh_extra_selections)

        self._apply_font_from_settings()
        self._update_gutter_width()
        self._refresh_extra_selections()
        self._emit_cursor_position()

    # ------------------------------------------------------------- public API

    def set_text(self, text: str) -> None:
        """Replace the editor contents with ``text``."""
        self.setPlainText(text)

    def get_text(self) -> str:
        """Return the current editor contents as a single string."""
        return self.toPlainText()

    def tab_width(self) -> int:
        """Return the number of spaces used for tab/indent operations."""
        if self._settings is None:
            return DEFAULT_TAB_WIDTH
        return int(self._settings.get("editor", "tab_width", DEFAULT_TAB_WIDTH))

    # --------------------------------------------------------- gutter support

    def line_number_area_width(self) -> int:
        """Return the pixel width needed to render the line-number gutter."""
        digits = max(2, len(str(max(1, self.blockCount()))))
        advance = self.fontMetrics().horizontalAdvance("9")
        return GUTTER_PADDING_PX + digits * advance

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        """Paint line numbers into the gutter; called by :class:`LineNumberArea`."""
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(DEFAULT_PALETTE.background_medium))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        offset = self.contentOffset()
        top = int(self.blockBoundingGeometry(block).translated(offset).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_line = self.textCursor().blockNumber()
        line_height = self.fontMetrics().height()
        width = self._line_number_area.width() - 4

        dim = QColor(DEFAULT_PALETTE.foreground_dim)
        bright = QColor(DEFAULT_PALETTE.amber_primary)
        align = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(bright if block_number == current_line else dim)
                painter.drawText(0, top, width, line_height, align, str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    # ---------------------------------------------------- Qt event overrides

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        """Keep the gutter flush with the editor's content rectangle."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(), self.line_number_area_width(), cr.height(),
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Convert Tab/Shift-Tab into space-based indent operations."""
        mods = event.modifiers()
        if event.key() == Qt.Key.Key_Tab and mods == Qt.KeyboardModifier.NoModifier:
            self._insert_spaces()
            return
        if event.key() == Qt.Key.Key_Backtab:
            self._outdent_line()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------- internal helpers

    def _apply_font_from_settings(self) -> None:
        """Apply the editor font from settings (or defaults)."""
        family = DEFAULT_FONT_FAMILY
        size = DEFAULT_FONT_SIZE
        if self._settings is not None:
            family = str(self._settings.get("editor", "font_family", family))
            size = int(self._settings.get("editor", "font_size", size))
        font = QFont(family)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(size)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * self.tab_width())

    def _update_gutter_width(self) -> None:
        """Refresh viewport margins whenever the gutter width may have changed."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _on_update_request(self, rect, dy: int) -> None:
        """Scroll or repaint the gutter in response to viewport updates."""
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height(),
            )
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def _emit_cursor_position(self) -> None:
        """Emit the current 1-based (line, column) for external listeners."""
        cursor = self.textCursor()
        self.cursor_position_changed_signal.emit(
            cursor.blockNumber() + 1, cursor.columnNumber() + 1,
        )

    def _refresh_extra_selections(self) -> None:
        """Rebuild the current-line and paren-match extra selections."""
        selections: list[QTextEdit.ExtraSelection] = []
        selections.append(self._current_line_selection())
        selections.extend(self._paren_match_selections())
        self.setExtraSelections(selections)

    def _current_line_selection(self) -> QTextEdit.ExtraSelection:
        """Build the subtle current-line background highlight."""
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(DEFAULT_PALETTE.background_light))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cursor = self.textCursor()
        cursor.clearSelection()
        sel.cursor = cursor
        return sel

    def _paren_match_selections(self) -> list[QTextEdit.ExtraSelection]:
        """Return highlight selections for the bracket pair around the cursor."""
        text = self.toPlainText()
        pos = self.textCursor().position()
        match = paren_matcher.find_matching(text, pos)
        if match is None:
            return []
        source = pos if pos < len(text) and text[pos] in "()[]{}" else pos - 1
        return [self._bracket_selection(source), self._bracket_selection(match)]

    def _bracket_selection(self, index: int) -> QTextEdit.ExtraSelection:
        """Build an amber-on-dark selection for the bracket at ``index``."""
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(DEFAULT_PALETTE.amber_primary))
        sel.format.setForeground(QColor(DEFAULT_PALETTE.background_dark))
        cursor = self.textCursor()
        cursor.setPosition(index)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            1,
        )
        sel.cursor = cursor
        return sel

    def _insert_spaces(self) -> None:
        """Insert ``tab_width`` spaces at the current cursor position."""
        self.textCursor().insertText(" " * self.tab_width())

    def _outdent_line(self) -> None:
        """Remove up to ``tab_width`` leading spaces from the current line."""
        width = self.tab_width()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        removed = 0
        while removed < width:
            cursor.movePosition(
                QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1,
            )
            if cursor.selectedText() != " ":
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                break
            cursor.removeSelectedText()
            removed += 1
        cursor.endEditBlock()
