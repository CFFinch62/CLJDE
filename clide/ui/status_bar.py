"""Three-section status bar for the CLIDE main window.

Exposes public update methods for the file info, cursor position, and
REPL status slots. Sections are plain ``QLabel`` widgets inserted as
permanent widgets on a standard ``QStatusBar`` so they stay visible
regardless of transient status messages.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QStatusBar, QWidget

from clide.config.theme import DEFAULT_PALETTE


class ClideStatusBar(QStatusBar):
    """Status bar with file info, cursor position, and REPL status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(True)

        self._file_label = QLabel("no file")
        self._cursor_label = QLabel("—")
        self._repl_label = QLabel("REPL: disconnected")

        self._file_label.setObjectName("statusFile")
        self._cursor_label.setObjectName("statusCursor")
        self._repl_label.setObjectName("statusRepl")

        for lbl in (self._file_label, self._cursor_label, self._repl_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            lbl.setMinimumWidth(80)

        self._cursor_label.setMinimumWidth(120)
        self._repl_label.setMinimumWidth(180)

        self._repl_label.setStyleSheet(f"color: {DEFAULT_PALETTE.foreground_dim};")

        self.addPermanentWidget(self._file_label, 3)
        self.addPermanentWidget(_separator(), 0)
        self.addPermanentWidget(self._cursor_label, 1)
        self.addPermanentWidget(_separator(), 0)
        self.addPermanentWidget(self._repl_label, 2)

    def set_file_info(self, text: str) -> None:
        """Set the left section (file path, encoding, dirty marker, etc.)."""
        self._file_label.setText(text or "no file")

    def set_cursor_position(self, line: int, column: int) -> None:
        """Set the middle section from a 1-based line/column pair."""
        self._cursor_label.setText(f"Ln {line}, Col {column}")

    def clear_cursor_position(self) -> None:
        """Clear the cursor position section when no editor is focused."""
        self._cursor_label.setText("—")

    def set_repl_status(
        self,
        text: str,
        *,
        connected: bool = False,
        error: bool = False,
    ) -> None:
        """Set the right section's REPL status text and colour."""
        self._repl_label.setText(text)
        if error:
            colour = DEFAULT_PALETTE.error_red
        elif connected:
            colour = DEFAULT_PALETTE.success_green
        else:
            colour = DEFAULT_PALETTE.foreground_dim
        self._repl_label.setStyleSheet(f"color: {colour};")

    def show_transient(self, message: str, timeout_ms: int = 4000) -> None:
        """Show a transient message that auto-clears after ``timeout_ms``."""
        self.showMessage(message, timeout_ms)


def _separator() -> QFrame:
    """Return a thin vertical separator frame for the status bar."""
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.VLine)
    frame.setFrameShadow(QFrame.Shadow.Plain)
    frame.setStyleSheet(f"color: {DEFAULT_PALETTE.background_light};")
    frame.setFixedWidth(2)
    return frame
