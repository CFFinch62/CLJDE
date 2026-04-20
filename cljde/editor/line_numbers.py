"""Line number gutter widget for the CLJDE editor.

The gutter is a thin ``QWidget`` that sits in the editor's viewport
margin. All geometry and painting decisions live on the owning
:class:`~cljde.editor.editor_widget.EditorWidget`; this widget is a
passive surface that delegates back via ``paint_line_numbers`` and
``line_number_area_width``. Keeping the logic in the editor means the
font metrics, current-line index, and palette can stay in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPaintEvent
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from cljde.editor.editor_widget import EditorWidget


class LineNumberArea(QWidget):
    """Thin gutter that paints line numbers to the left of the editor."""

    def __init__(self, editor: "EditorWidget") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        """Return a size hint driven by the editor's width calculation."""
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Delegate painting back to the owning editor."""
        self._editor.paint_line_numbers(event)
