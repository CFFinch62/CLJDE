"""Clojure form boundary detection.

Exposes pure functions for classifying each character of a source text
as code, string, line-comment, or character-literal, and for locating
the innermost (or top-level) balanced bracketed form enclosing a given
cursor position.

The classifier is deliberately not a full Clojure reader: it treats
``(``, ``[``, ``{`` as equivalent open brackets and their closers as
equivalent close brackets, while keeping string and character-literal
content out of the bracket count.
"""

from __future__ import annotations

import re

CODE = 0
STRING = 1
COMMENT = 2
CHAR_LITERAL = 3

OPEN_BRACKETS = "([{"
CLOSE_BRACKETS = ")]}"
BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}


def classify(text: str) -> list[int]:
    """Return a per-character list of :data:`CODE`/:data:`STRING`/etc."""
    n = len(text)
    out = [CODE] * n
    i = 0
    while i < n:
        c = text[i]
        if c == ";":
            while i < n and text[i] != "\n":
                out[i] = COMMENT
                i += 1
            continue
        if c == '"':
            out[i] = STRING
            i += 1
            while i < n:
                ch = text[i]
                out[i] = STRING
                if ch == "\\" and i + 1 < n:
                    i += 1
                    out[i] = STRING
                    i += 1
                    continue
                i += 1
                if ch == '"':
                    break
            continue
        if c == "\\":
            out[i] = CHAR_LITERAL
            i += 1
            if i < n:
                out[i] = CHAR_LITERAL
                i += 1
                while i < n and text[i].isalpha():
                    out[i] = CHAR_LITERAL
                    i += 1
            continue
        i += 1
    return out


def form_at(text: str, pos: int) -> tuple[int, int] | None:
    """Return ``(start, end)`` of the innermost balanced form containing ``pos``.

    ``end`` is exclusive (Python half-open slice convention). Returns
    ``None`` when ``pos`` is in whitespace between forms, inside a
    comment, inside a top-level string, or when no balanced bracketed
    form contains ``pos``.
    """
    if not _pos_in_range(text, pos):
        return None
    classes = classify(text)
    if pos < len(text) and classes[pos] == COMMENT:
        return None

    candidates: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, c in enumerate(text):
        if classes[i] != CODE:
            continue
        if c in OPEN_BRACKETS:
            stack.append(i)
        elif c in CLOSE_BRACKETS:
            if not stack:
                continue
            start = stack.pop()
            if BRACKET_PAIRS.get(text[start]) != c:
                continue
            if start <= pos <= i:
                candidates.append((start, i + 1))

    if not candidates:
        return None
    candidates.sort(key=lambda se: se[1] - se[0])
    return candidates[0]


def top_level_form_at(text: str, pos: int) -> tuple[int, int] | None:
    """Return ``(start, end)`` of the top-level form containing ``pos``."""
    if not _pos_in_range(text, pos):
        return None
    classes = classify(text)
    if pos < len(text) and classes[pos] == COMMENT:
        return None

    stack: list[int] = []
    for i, c in enumerate(text):
        if classes[i] != CODE:
            continue
        if c in OPEN_BRACKETS:
            stack.append(i)
        elif c in CLOSE_BRACKETS:
            if not stack:
                continue
            start = stack.pop()
            if BRACKET_PAIRS.get(text[start]) != c:
                continue
            if not stack and start <= pos <= i:
                return (start, i + 1)
    return None


def _pos_in_range(text: str, pos: int) -> bool:
    """Return True if ``pos`` is a valid cursor index for ``text``."""
    return 0 <= pos <= len(text)


_NS_OPEN_RE = re.compile(r"\(\s*ns\s")
_NAME_STOP = set(" \t\r\n()[]{}\"',;")


def detect_file_namespace(text: str) -> str | None:
    """Return the name from the first top-level ``(ns ...)`` form, if any.

    Tolerates optional ``^meta`` forms between ``ns`` and the name
    (e.g. ``(ns ^:doc my.ns)``). Ignores ``(ns ...)`` occurrences found
    inside strings or comments via the classifier.
    """
    classes = classify(text)
    n = len(text)
    for match in _NS_OPEN_RE.finditer(text):
        if classes[match.start()] != CODE:
            continue
        i = match.end()
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            if ch == "^":
                i = _skip_metadata(text, i + 1)
                continue
            if ch in "()[]{}\"',;":
                break
            start = i
            while i < n and text[i] not in _NAME_STOP:
                i += 1
            name = text[start:i]
            return name or None
    return None


def _skip_metadata(text: str, i: int) -> int:
    """Skip past a ``^``-prefixed metadata form; return index after it."""
    n = len(text)
    if i >= n:
        return i
    if text[i] == "{":
        depth = 1
        i += 1
        while i < n and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        return i
    while i < n and text[i] not in _NAME_STOP:
        i += 1
    return i
