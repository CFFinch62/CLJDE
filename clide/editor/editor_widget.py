"""CLIDE source-editor widget.

Extends :class:`QPlainTextEdit` with a line-number gutter, current-line
and paren-match highlighting, Clojure syntax highlighting, debounced
balance checking (red wavy underlines), structural edits
(slurp/barf/wrap/unwrap), rainbow-parens toggle, and space-based
indent. Accepts an optional :class:`Settings` so font, tab width, and
rainbow state can be read at construction.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QWidget

from clide.config.settings import Settings
from clide.config.theme import DEFAULT_PALETTE
from clide.editor import balance_checker, paren_matcher, structural_edit
from clide.editor.clojure_highlighter import ClojureHighlighter
from clide.editor.line_numbers import LineNumberArea

DEFAULT_FONT_FAMILY = "monospace"
DEFAULT_FONT_SIZE = 11
DEFAULT_TAB_WIDTH = 2
GUTTER_PADDING_PX = 12
BALANCE_CHECK_INTERVAL_MS = 500

_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
_M = Qt.KeyboardModifier
_CHORD_MASK = _M.ShiftModifier | _M.ControlModifier | _M.AltModifier | _M.MetaModifier


class EditorWidget(QPlainTextEdit):
    """Clojure source editor with line numbers, paren match, and highlighting."""

    cursor_position_changed_signal = pyqtSignal(int, int)
    notice_signal = pyqtSignal(str)

    def __init__(
        self,
        settings: Settings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._file_path: str | None = None
        self._line_number_area = LineNumberArea(self)
        self._highlighter = ClojureHighlighter(self.document())
        self._balance_selections: list[QTextEdit.ExtraSelection] = []
        self._wrap_pending = False

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFrameStyle(0)

        self._balance_timer = QTimer(self)
        self._balance_timer.setSingleShot(True)
        self._balance_timer.setInterval(BALANCE_CHECK_INTERVAL_MS)
        self._balance_timer.timeout.connect(self._run_balance_check)

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._on_update_request)
        self.cursorPositionChanged.connect(self._emit_cursor_position)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self.textChanged.connect(self._refresh_extra_selections)
        self.textChanged.connect(self._balance_timer.start)

        self._apply_font_from_settings()
        self._apply_rainbow_from_settings()
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

    def file_path(self) -> str | None:
        """Return the filesystem path associated with this editor, if any."""
        return self._file_path

    def set_file_path(self, path: str | None) -> None:
        """Associate a filesystem path with this editor (or clear it)."""
        self._file_path = path

    def cursor_line_column(self) -> tuple[int, int]:
        """Return the current cursor position as 1-based (line, column)."""
        cursor = self.textCursor()
        return cursor.blockNumber() + 1, cursor.columnNumber() + 1

    def set_cursor_line_column(self, line: int, column: int) -> None:
        """Move the cursor to 1-based (line, column); clamped to document."""
        doc = self.document()
        block = doc.findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            block = doc.lastBlock()
        col = max(0, min(column - 1, block.length() - 1))
        cursor = self.textCursor()
        cursor.setPosition(block.position() + col)
        self.setTextCursor(cursor)

    def set_rainbow_parens(self, enabled: bool) -> None:
        """Toggle rainbow-parens shading on the embedded highlighter."""
        self._highlighter.set_rainbow(enabled)

    # ------------------------------------------------------ structural edits

    def slurp_forward(self) -> None:
        """Extend the innermost form at the cursor to swallow its next sibling."""
        self._run_structural(structural_edit.slurp_forward, "Nothing to slurp")

    def barf_forward(self) -> None:
        """Eject the last child of the innermost form at the cursor."""
        self._run_structural(structural_edit.barf_forward, "Nothing to barf")

    def wrap_form(self, open_char: str) -> None:
        """Wrap the current selection (or innermost form) with ``open_char``."""
        close_char = _BRACKET_PAIRS.get(open_char)
        if close_char is None:
            return
        text = self.toPlainText()
        cursor = self.textCursor()
        if cursor.hasSelection():
            result = structural_edit.wrap_range(
                text, cursor.selectionStart(), cursor.selectionEnd(),
                open_char, close_char,
            )
        else:
            result = structural_edit.wrap_form(
                text, cursor.position(), open_char, close_char,
            )
        if result is None:
            self._notify_failure("Nothing to wrap")
            return
        self._apply_structural_edit(*result)

    def unwrap_form(self) -> None:
        """Replace the innermost form at the cursor with its contents."""
        self._run_structural(structural_edit.unwrap_form, "Nothing to unwrap")

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
        """Handle structural-edit chords and space-based indent operations."""
        key = event.key()
        chord = event.modifiers() & _CHORD_MASK
        alt = Qt.KeyboardModifier.AltModifier
        alt_shift = alt | Qt.KeyboardModifier.ShiftModifier

        if self._wrap_pending:
            self._wrap_pending = False
            text_pressed = event.text()
            if text_pressed in _BRACKET_PAIRS:
                self.wrap_form(text_pressed)
                return

        if chord == alt_shift and key == Qt.Key.Key_Right:
            self.slurp_forward()
            return
        if chord == alt_shift and key == Qt.Key.Key_Left:
            self.barf_forward()
            return
        if chord == alt and key == Qt.Key.Key_W:
            self._wrap_pending = True
            self.notice_signal.emit("Wrap with ( [ or {")
            return
        if chord == alt and key == Qt.Key.Key_U:
            self.unwrap_form()
            return
        if key == Qt.Key.Key_Tab and chord == Qt.KeyboardModifier.NoModifier:
            self._insert_spaces()
            return
        if key == Qt.Key.Key_Backtab:
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
        """Rebuild the current-line, paren-match, and balance-error selections."""
        selections: list[QTextEdit.ExtraSelection] = []
        selections.append(self._current_line_selection())
        selections.extend(self._paren_match_selections())
        selections.extend(self._balance_selections)
        self.setExtraSelections(selections)

    def _apply_rainbow_from_settings(self) -> None:
        """Apply the initial rainbow-parens flag from settings, if present."""
        if self._settings is None:
            return
        enabled = bool(self._settings.get("editor", "rainbow_parens", False))
        self._highlighter.set_rainbow(enabled)

    def _run_balance_check(self) -> None:
        """Recompute balance underlines and refresh the extra-selection list."""
        errors = balance_checker.check_balance(self.toPlainText())
        self._balance_selections = [self._balance_selection(err.pos) for err in errors]
        self._refresh_extra_selections()

    def _balance_selection(self, index: int) -> QTextEdit.ExtraSelection:
        """Build a red wavy-underline selection at ``index``."""
        sel = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        fmt.setUnderlineColor(QColor(DEFAULT_PALETTE.error_red))
        sel.format = fmt
        cursor = self.textCursor()
        cursor.setPosition(index)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
        sel.cursor = cursor
        return sel

    def _run_structural(self, op, failure_message: str) -> None:
        """Invoke ``op(text, pos)`` and apply the result, or beep on failure."""
        text = self.toPlainText()
        pos = self.textCursor().position()
        result = op(text, pos)
        if result is None:
            self._notify_failure(failure_message)
            return
        self._apply_structural_edit(*result)

    def _apply_structural_edit(self, new_text: str, new_pos: int) -> None:
        """Replace the document with ``new_text`` in one undoable transaction."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(new_text)
        cursor.setPosition(max(0, min(new_pos, len(new_text))))
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def _notify_failure(self, message: str) -> None:
        """Beep and emit a notice for failed structural edits."""
        QApplication.beep()
        self.notice_signal.emit(message)

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
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
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
