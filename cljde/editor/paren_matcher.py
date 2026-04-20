"""Bracket matching for the CLJDE editor.

Exposes a single public function, :func:`find_matching`, which returns
the index of the bracket that pairs with the one adjacent to the given
cursor position. Brackets inside strings, line comments, and character
literals are ignored via the shared classifier in
:mod:`cljde.editor.form_detector`.
"""

from __future__ import annotations

from cljde.editor.form_detector import (
    CLOSE_BRACKETS,
    CODE,
    OPEN_BRACKETS,
    classify,
)

_MATCH: dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    ")": "(",
    "]": "[",
    "}": "{",
}


def find_matching(text: str, pos: int) -> int | None:
    """Return the index of the bracket matching the one adjacent to ``pos``.

    ``pos`` is interpreted as a cursor index between characters. The
    bracket at ``text[pos]`` (cursor immediately before the bracket)
    is preferred; if that character is not a bracket the bracket at
    ``text[pos - 1]`` (cursor immediately after) is considered. Returns
    ``None`` if neither adjacent character is a code-context bracket,
    or if the bracket is unmatched.
    """
    if not text:
        return None
    classes = classify(text)
    candidate = _bracket_adjacent(text, classes, pos)
    if candidate is None:
        return None
    opener = text[candidate]
    if opener in OPEN_BRACKETS:
        return _scan_forward(text, classes, candidate)
    return _scan_backward(text, classes, candidate)


def _bracket_adjacent(text: str, classes: list[int], pos: int) -> int | None:
    """Return the code-context bracket index adjacent to ``pos``, if any."""
    n = len(text)
    if 0 <= pos < n and classes[pos] == CODE and text[pos] in OPEN_BRACKETS + CLOSE_BRACKETS:
        return pos
    prev = pos - 1
    if 0 <= prev < n and classes[prev] == CODE and text[prev] in OPEN_BRACKETS + CLOSE_BRACKETS:
        return prev
    return None


def _scan_forward(text: str, classes: list[int], open_idx: int) -> int | None:
    """Return the index of the closer matching the opener at ``open_idx``."""
    depth = 0
    expected = _MATCH[text[open_idx]]
    for i in range(open_idx, len(text)):
        if classes[i] != CODE:
            continue
        c = text[i]
        if c in OPEN_BRACKETS:
            depth += 1
        elif c in CLOSE_BRACKETS:
            depth -= 1
            if depth == 0:
                return i if c == expected else None
    return None


def _scan_backward(text: str, classes: list[int], close_idx: int) -> int | None:
    """Return the index of the opener matching the closer at ``close_idx``."""
    depth = 0
    expected = _MATCH[text[close_idx]]
    for i in range(close_idx, -1, -1):
        if classes[i] != CODE:
            continue
        c = text[i]
        if c in CLOSE_BRACKETS:
            depth += 1
        elif c in OPEN_BRACKETS:
            depth -= 1
            if depth == 0:
                return i if c == expected else None
    return None
