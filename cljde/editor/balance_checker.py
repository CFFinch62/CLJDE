"""Bracket-balance checker for Clojure source text.

Pure functions: classify characters via
:func:`cljde.editor.form_detector.classify` so brackets inside strings,
line comments, and character literals are ignored, then walk the text
once to collect :class:`BalanceError` entries for every unmatched open,
unmatched close, and open/close mismatch.

The editor widget uses the resulting list to draw red wavy underlines
at the problem positions on a debounced timer.
"""

from __future__ import annotations

from dataclasses import dataclass

from cljde.editor.form_detector import (
    BRACKET_PAIRS,
    CLOSE_BRACKETS,
    CODE,
    OPEN_BRACKETS,
    classify,
)

KIND_UNMATCHED_OPEN = "unmatched_open"
KIND_UNMATCHED_CLOSE = "unmatched_close"
KIND_MISMATCH = "mismatch"


@dataclass(frozen=True)
class BalanceError:
    """A single bracket-balance problem in the source text."""

    pos: int
    kind: str
    char: str


def check_balance(text: str) -> list[BalanceError]:
    """Return all bracket-balance errors in ``text``, sorted by position.

    Each returned :class:`BalanceError` has ``pos`` pointing at the
    offending bracket character. ``kind`` is one of
    :data:`KIND_UNMATCHED_OPEN`, :data:`KIND_UNMATCHED_CLOSE`,
    :data:`KIND_MISMATCH`.
    """
    if not text:
        return []
    classes = classify(text)
    stack: list[tuple[int, str]] = []
    errors: list[BalanceError] = []
    for i, c in enumerate(text):
        if classes[i] != CODE:
            continue
        if c in OPEN_BRACKETS:
            stack.append((i, c))
        elif c in CLOSE_BRACKETS:
            if not stack:
                errors.append(BalanceError(i, KIND_UNMATCHED_CLOSE, c))
                continue
            _open_pos, open_char = stack.pop()
            expected = BRACKET_PAIRS[open_char]
            if c != expected:
                errors.append(BalanceError(i, KIND_MISMATCH, c))
    for pos, char in stack:
        errors.append(BalanceError(pos, KIND_UNMATCHED_OPEN, char))
    errors.sort(key=lambda err: err.pos)
    return errors
