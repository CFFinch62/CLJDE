"""Tests for :mod:`cljde.editor.structural_edit`.

Exercises slurp/barf/wrap/unwrap on representative Clojure fragments:
single-sibling slurp, last-child barf, wrap of the innermost form and
explicit ranges, and unwrap retaining the inner content.
"""

from __future__ import annotations

from cljde.editor.structural_edit import (
    barf_forward,
    slurp_forward,
    unwrap_form,
    wrap_form,
    wrap_range,
)


# --------------------------------------------------------------- slurp_forward

def test_slurp_forward_absorbs_next_sibling() -> None:
    """``slurp_forward`` moves the next atom inside the trailing close."""
    text = "(foo) bar"
    pos = 2
    result = slurp_forward(text, pos)
    assert result is not None
    new_text, _new_pos = result
    assert new_text == "(foo bar)"


def test_slurp_forward_no_sibling_returns_none() -> None:
    """With nothing after the form, slurp returns ``None``."""
    text = "(foo)"
    assert slurp_forward(text, 2) is None


def test_slurp_forward_absorbs_nested_form() -> None:
    """Slurp can pull a bracketed sibling inside."""
    text = "(a) [b c]"
    result = slurp_forward(text, 1)
    assert result is not None
    new_text, _pos = result
    assert new_text == "(a [b c])"


# ---------------------------------------------------------------- barf_forward

def test_barf_forward_ejects_last_child() -> None:
    """``barf_forward`` moves the last child outside the closing bracket."""
    text = "(foo bar)"
    result = barf_forward(text, 1)
    assert result is not None
    new_text, _pos = result
    assert new_text == "(foo) bar"


def test_barf_forward_single_child_returns_none() -> None:
    """With a single child there is nothing to barf."""
    text = "(foo)"
    assert barf_forward(text, 1) is None


def test_barf_forward_nested_child() -> None:
    """Nested children are moved as a whole unit."""
    text = "(a b [c d])"
    result = barf_forward(text, 1)
    assert result is not None
    new_text, _pos = result
    assert new_text == "(a b) [c d]"


# --------------------------------------------------------------------- wrap

def test_wrap_form_wraps_innermost_at_pos() -> None:
    """``wrap_form`` wraps the nearest form around ``pos``."""
    text = "(a b)"
    result = wrap_form(text, 2, "[", "]")
    assert result is not None
    new_text, new_pos = result
    assert new_text == "[(a b)]"
    assert new_pos == 1


def test_wrap_form_no_form_returns_none() -> None:
    """With no enclosing form at ``pos``, wrap returns ``None``."""
    assert wrap_form("   ", 1, "(", ")") is None


def test_wrap_range_wraps_explicit_slice() -> None:
    """``wrap_range`` wraps the half-open range verbatim."""
    text = "abc def"
    new_text, new_pos = wrap_range(text, 0, 3, "(", ")")
    assert new_text == "(abc) def"
    assert new_pos == 1


# ------------------------------------------------------------------- unwrap

def test_unwrap_form_keeps_contents() -> None:
    """``unwrap_form`` strips the outer brackets from the innermost form."""
    text = "(foo bar)"
    result = unwrap_form(text, 3)
    assert result is not None
    new_text, _pos = result
    assert new_text == "foo bar"


def test_unwrap_form_no_form_returns_none() -> None:
    """Unwrap on whitespace returns ``None``."""
    assert unwrap_form("   ", 1) is None


def test_unwrap_form_nested_unwraps_innermost() -> None:
    """Unwrap peels only the innermost form, leaving outer brackets intact."""
    text = "(a [b c] d)"
    result = unwrap_form(text, 5)
    assert result is not None
    new_text, _pos = result
    assert new_text == "(a b c d)"


def test_unwrap_form_at_inner_opener_prefers_outer() -> None:
    """Cursor on an inner opening bracket unwraps the enclosing parent."""
    text = "[(foo bar)]"
    result = unwrap_form(text, 1)
    assert result is not None
    new_text, _pos = result
    assert new_text == "(foo bar)"


def test_wrap_then_unwrap_is_identity() -> None:
    """``wrap_form`` followed by ``unwrap_form`` at the returned pos round-trips."""
    text = "(foo bar)"
    wrapped = wrap_form(text, 4, "[", "]")
    assert wrapped is not None
    new_text, new_pos = wrapped
    assert new_text == "[(foo bar)]"
    restored = unwrap_form(new_text, new_pos)
    assert restored is not None
    assert restored[0] == text
