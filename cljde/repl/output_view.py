"""Read-only REPL output view with category-styled text.

Each message category (``command``, ``value``, ``stdout``, ``stderr``,
``exception``, ``info``) is rendered with a distinct
:class:`QTextCharFormat`. The view caps its backlog at
``repl.max_history_lines`` from :class:`Settings` (default 5000),
trimming oldest blocks on overflow. Auto-scroll follows new output
unless the user has scrolled up, in which case the current position is
preserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QTextEdit, QWidget

from cljde.config.theme import DEFAULT_PALETTE

if TYPE_CHECKING:
    from cljde.config.settings import Settings

DEFAULT_MAX_LINES = 5000
SCROLL_LOCK_EPSILON = 2


class OutputView(QTextEdit):
    """Themed, read-only, interleaved transcript of REPL activity."""

    def __init__(
        self,
        settings: "Settings | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_lines = _resolve_max_lines(settings)
        self._formats = _build_formats()

        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setObjectName("replOutputView")

        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.setFont(font)

    # ------------------------------------------------------------ public API

    def append_command(self, code: str, ns: str) -> None:
        """Echo an expression being sent for evaluation, prefixed ``=>``."""
        prefix = f"{ns}=> " if ns else "=> "
        self._append_block(prefix + code.rstrip("\n") + "\n", self._formats["command"])

    def append_value(self, value: str, ns: str) -> None:
        """Append the return value of an eval."""
        self._append_block((value or "").rstrip("\n") + "\n", self._formats["value"])

    def append_stdout(self, text: str) -> None:
        """Append captured ``*out*`` text verbatim."""
        self._append_block(text, self._formats["stdout"])

    def append_stderr(self, text: str) -> None:
        """Append captured ``*err*`` text verbatim."""
        self._append_block(text, self._formats["stderr"])

    def append_exception(self, ex_class: str, message: str, trace: str) -> None:
        """Render an exception in red; ``trace`` is appended below if present."""
        header_bits = [b for b in (ex_class, message) if b]
        header = " ".join(header_bits).strip() or "exception"
        self._append_block(header + "\n", self._formats["exception"])
        if trace:
            self._append_block(trace.rstrip("\n") + "\n", self._formats["stderr"])

    def append_info(self, text: str) -> None:
        """Append a system/status line in the info colour."""
        self._append_block(text.rstrip("\n") + "\n", self._formats["info"])

    def clear(self) -> None:
        """Drop all transcript content."""
        super().clear()

    # ---------------------------------------------------------- internals

    def _append_block(self, text: str, fmt: QTextCharFormat) -> None:
        """Insert ``text`` with ``fmt``, enforcing trim and scroll policy."""
        if not text:
            return
        sb = self.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - SCROLL_LOCK_EPSILON

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)

        self._enforce_max_lines()

        if at_bottom:
            sb.setValue(sb.maximum())

    def _enforce_max_lines(self) -> None:
        """Drop the oldest blocks when the document exceeds ``_max_lines``."""
        doc = self.document()
        excess = doc.blockCount() - self._max_lines
        if excess <= 0:
            return
        cut = QTextCursor(doc)
        cut.setPosition(0)
        cut.setPosition(
            doc.findBlockByNumber(excess).position(),
            QTextCursor.MoveMode.KeepAnchor,
        )
        cut.removeSelectedText()


def _resolve_max_lines(settings: "Settings | None") -> int:
    """Return the configured backlog cap, falling back to the default."""
    if settings is None:
        return DEFAULT_MAX_LINES
    try:
        value = int(settings.get("repl", "max_history_lines", DEFAULT_MAX_LINES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_LINES
    return value if value > 0 else DEFAULT_MAX_LINES


def _build_formats() -> dict[str, QTextCharFormat]:
    """Assemble the category -> ``QTextCharFormat`` lookup table."""
    p = DEFAULT_PALETTE
    formats: dict[str, QTextCharFormat] = {}

    command = QTextCharFormat()
    command.setForeground(QColor(p.amber_bright))
    command.setFontWeight(QFont.Weight.Bold)
    formats["command"] = command

    value = QTextCharFormat()
    value.setForeground(QColor(p.foreground))
    formats["value"] = value

    stdout = QTextCharFormat()
    stdout.setForeground(QColor(p.foreground_dim))
    formats["stdout"] = stdout

    stderr = QTextCharFormat()
    stderr.setForeground(QColor(p.error_red))
    formats["stderr"] = stderr

    exception = QTextCharFormat()
    exception.setForeground(QColor(p.error_red))
    exception.setFontWeight(QFont.Weight.Bold)
    formats["exception"] = exception

    info = QTextCharFormat()
    info.setForeground(QColor(p.blue_primary))
    formats["info"] = info

    return formats
