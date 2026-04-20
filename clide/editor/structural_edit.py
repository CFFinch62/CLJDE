"""Structural edits for Clojure source text.

Pure functions of ``(text, pos, ...)`` returning
``(new_text, new_pos)`` or ``None`` when the operation is impossible
(malformed code, no form at cursor, etc.). The editor widget wraps
these in a single :class:`QTextCursor` transaction so undo applies to
the whole move.

Operations exposed:

  * :func:`slurp_forward` — extend the innermost form to swallow its
    next sibling.
  * :func:`barf_forward` — eject the last child of the innermost form
    into the parent.
  * :func:`wrap_form` — wrap the innermost form at ``pos`` with a
    bracket pair.
  * :func:`wrap_range` — wrap a half-open range ``[start:end)`` with a
    bracket pair (used for selection-based wrapping).
  * :func:`unwrap_form` — replace the innermost form with its contents.
"""

from __future__ import annotations

from clide.editor.form_detector import (
    CLOSE_BRACKETS,
    CODE,
    COMMENT,
    OPEN_BRACKETS,
    STRING,
    classify,
    form_at,
)


def slurp_forward(text: str, pos: int) -> tuple[str, int] | None:
    """Extend the form containing ``pos`` to include its next sibling."""
    bounds = form_at(text, pos)
    if bounds is None:
        return None
    start, end = bounds
    close_pos = end - 1
    sibling = _next_form_after(text, end)
    if sibling is None:
        return None
    sib_s, sib_e = sibling
    new_text = (
        text[:close_pos]
        + text[end:sib_e]
        + text[close_pos:end]
        + text[sib_e:]
    )
    return new_text, pos


def barf_forward(text: str, pos: int) -> tuple[str, int] | None:
    """Eject the last child of the form containing ``pos`` to its parent."""
    bounds = form_at(text, pos)
    if bounds is None:
        return None
    start, end = bounds
    close_pos = end - 1
    children = _children_of(text, start, end)
    if len(children) < 2:
        return None
    last_s, last_e = children[-1]
    ws_start = _rewind_whitespace(text, last_s)
    if ws_start == last_s:
        return None
    close_bracket = text[close_pos:end]
    new_text = (
        text[:ws_start]
        + close_bracket
        + text[ws_start:last_s]
        + text[last_s:last_e]
        + text[end:]
    )
    new_close = ws_start
    new_pos = min(pos, new_close)
    return new_text, new_pos


def wrap_range(
    text: str, start: int, end: int, open_char: str, close_char: str,
) -> tuple[str, int]:
    """Wrap ``text[start:end]`` with ``open_char`` and ``close_char``."""
    new_text = text[:start] + open_char + text[start:end] + close_char + text[end:]
    return new_text, start + 1


def wrap_form(
    text: str, pos: int, open_char: str, close_char: str,
) -> tuple[str, int] | None:
    """Wrap the innermost form at ``pos`` with ``open_char``/``close_char``."""
    bounds = form_at(text, pos)
    if bounds is None:
        return None
    return wrap_range(text, bounds[0], bounds[1], open_char, close_char)


def unwrap_form(text: str, pos: int) -> tuple[str, int] | None:
    """Replace the innermost form at ``pos`` with its bracketed contents.

    When ``pos`` sits exactly on an inner form's opening bracket and a
    strictly-enclosing parent form also contains ``pos``, the parent is
    preferred. This makes ``unwrap_form`` the inverse of ``wrap_form``
    (which leaves the cursor just after the new opening bracket, i.e.
    on the wrapped form's opener).
    """
    bounds = form_at(text, pos)
    if bounds is None:
        return None
    start, end = bounds
    if pos == start and start > 0 and pos < len(text) and text[pos] in "([{":
        outer = form_at(text, pos - 1)
        if outer is not None and outer != bounds:
            start, end = outer
    inner = text[start + 1:end - 1]
    new_text = text[:start] + inner + text[end:]
    new_pos = max(start, pos - 1)
    return new_text, new_pos


# --------------------------------------------------------------- helpers


def _next_form_after(text: str, pos: int) -> tuple[int, int] | None:
    """Return the ``(start, end)`` of the next form/atom at or after ``pos``."""
    classes = classify(text)
    n = len(text)
    i = pos
    while i < n:
        cls = classes[i]
        c = text[i]
        if cls == COMMENT:
            i += 1
            continue
        if cls == CODE and c.isspace():
            i += 1
            continue
        if cls == CODE and c in CLOSE_BRACKETS:
            return None
        break
    if i >= n:
        return None
    return _extent_from(text, classes, i)


def _children_of(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Return top-level child extents inside the form at ``[start, end)``."""
    classes = classify(text)
    children: list[tuple[int, int]] = []
    limit = end - 1
    i = start + 1
    while i < limit:
        cls = classes[i]
        c = text[i]
        if cls == CODE and c.isspace():
            i += 1
            continue
        if cls == COMMENT:
            i += 1
            continue
        extent = _extent_from(text, classes, i)
        if extent is None:
            i += 1
            continue
        if extent[1] > limit + 1:
            break
        children.append(extent)
        i = extent[1]
    return children


def _extent_from(
    text: str, classes: list[int], i: int,
) -> tuple[int, int] | None:
    """Return the extent of the form/atom starting at ``i``."""
    n = len(text)
    cls = classes[i]
    c = text[i]
    if cls == CODE and c in OPEN_BRACKETS:
        depth = 1
        j = i + 1
        while j < n:
            if classes[j] == CODE:
                if text[j] in OPEN_BRACKETS:
                    depth += 1
                elif text[j] in CLOSE_BRACKETS:
                    depth -= 1
                    if depth == 0:
                        return i, j + 1
            j += 1
        return None
    if cls == STRING:
        j = i + 1
        while j < n and classes[j] == STRING:
            j += 1
        return i, j
    j = i
    while j < n and classes[j] == CODE:
        ch = text[j]
        if ch.isspace() or ch in OPEN_BRACKETS or ch in CLOSE_BRACKETS:
            break
        j += 1
    if j == i:
        return None
    return i, j


def _rewind_whitespace(text: str, pos: int) -> int:
    """Return the earliest index whose text up to ``pos`` is all whitespace."""
    i = pos
    while i > 0 and text[i - 1] in " \t\r\n":
        i -= 1
    return i
