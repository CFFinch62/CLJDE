"""Rainbow-parens support for the CLIDE Clojure highlighter.

The highlighter stacks poorly when paired with a second
:class:`QSyntaxHighlighter`, so rainbow-parens is implemented as an
in-place extension of :class:`ClojureHighlighter` rather than a
separate highlighter. This module contributes:

  * :func:`build_rainbow_formats` — precomputes a list of
    :class:`QTextCharFormat` objects coloured from
    :attr:`Palette.rainbow_cycle`, suitable for direct use in
    ``QSyntaxHighlighter.setFormat``.
  * :func:`format_for_depth` — selects a format by nesting depth,
    wrapping modulo the palette length.

The highlighter itself owns the enable/disable flag and carries the
running bracket depth across blocks via block state.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QTextCharFormat

from clide.config.theme import DEFAULT_PALETTE, Palette


def build_rainbow_formats(
    palette: Palette = DEFAULT_PALETTE,
) -> list[QTextCharFormat]:
    """Return one :class:`QTextCharFormat` per colour in ``rainbow_cycle``."""
    formats: list[QTextCharFormat] = []
    for colour in palette.rainbow_cycle:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colour))
        formats.append(fmt)
    return formats


def format_for_depth(
    formats: list[QTextCharFormat], depth: int,
) -> QTextCharFormat:
    """Return the rainbow format for ``depth`` (wraps modulo palette size)."""
    if not formats:
        return QTextCharFormat()
    return formats[depth % len(formats)]
