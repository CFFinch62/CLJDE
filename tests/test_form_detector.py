"""Tests for :mod:`cljde.editor.form_detector`.

Covers the boundary cases called out in the Phase 2 spec: nested forms,
whitespace between top-level forms, strings (both standalone and
enclosing), line comments, character literals that look like brackets,
unbalanced input, and out-of-range cursor positions.
"""

from __future__ import annotations

from cljde.editor.form_detector import (
    CHAR_LITERAL,
    CODE,
    COMMENT,
    STRING,
    classify,
    form_at,
    top_level_form_at,
)


# ----------------------------------------------------------------- classify

def test_classify_line_comment() -> None:
    """``;`` starts a line comment that extends to the newline."""
    text = "(foo) ; bar\n(baz)"
    classes = classify(text)
    assert classes[6] == COMMENT  # ';'
    assert classes[10] == COMMENT  # 'r'
    assert classes[11] == CODE  # '\n' is outside the comment
    assert classes[12] == CODE  # '(' of (baz)


def test_classify_string_with_escape() -> None:
    """``\\"`` inside a string does not end the string."""
    text = '"a\\"b"'
    classes = classify(text)
    assert all(cls == STRING for cls in classes)


def test_classify_char_literal() -> None:
    """A ``\\`` introduces a character literal; named forms are consumed."""
    text = "\\newline x"
    classes = classify(text)
    # indices 0..7 are '\newline'
    for i in range(8):
        assert classes[i] == CHAR_LITERAL
    # ' ' and 'x' are code context
    assert classes[8] == CODE
    assert classes[9] == CODE


# ------------------------------------------------------------------ form_at

def test_form_at_top_level_defn() -> None:
    """Cursor inside a top-level ``(defn ...)`` returns its bounds."""
    text = "(defn foo [x] x)"
    assert form_at(text, 7) == (0, 16)


def test_form_at_innermost_vector() -> None:
    """Cursor inside a nested vector returns the vector, not the outer form."""
    text = "(defn foo [x] (let [y 1] (+ x y)))"
    #            0         1         2         3
    #            0123456789012345678901234567890123
    # (let at 14..32, [y 1] at 19..23, (+ x y) at 25..31
    assert form_at(text, 20) == (19, 24)     # cursor on 'y' inside [y 1]


def test_form_at_innermost_call() -> None:
    """Cursor inside ``(+ x y)`` returns those bounds."""
    text = "(defn foo [x] (let [y 1] (+ x y)))"
    assert form_at(text, 26) == (25, 32)     # cursor on '+'


def test_form_at_whitespace_between_vector_and_call() -> None:
    """Cursor on the space between ``]`` and ``(`` inside a let returns the let."""
    text = "(defn foo [x] (let [y 1] (+ x y)))"
    assert form_at(text, 24) == (14, 33)     # pos 24 is the space


def test_top_level_form_at_from_nested() -> None:
    """``top_level_form_at`` returns the outermost form regardless of depth."""
    text = "(defn foo [x] (let [y 1] (+ x y)))"
    assert top_level_form_at(text, 20) == (0, 34)
    assert top_level_form_at(text, 26) == (0, 34)


def test_whitespace_between_top_level_forms_is_none() -> None:
    """Cursor on whitespace between two top-level forms returns ``None``."""
    text = "(foo)  (bar)"
    assert form_at(text, 5) is None
    assert form_at(text, 6) is None
    assert top_level_form_at(text, 5) is None


def test_string_contents_do_not_confuse_bracket_count() -> None:
    """Brackets inside a string are ignored for form detection."""
    text = '(println "foo (bar)")'
    assert form_at(text, 15) == (0, 21)  # cursor inside the string


def test_cursor_in_line_comment_is_none() -> None:
    """Cursor inside a ``;`` line comment returns ``None``."""
    text = "(foo) ; a comment\n(bar)"
    assert form_at(text, 10) is None


def test_cursor_at_open_bracket_returns_form() -> None:
    """Cursor exactly on the opening bracket returns that form."""
    text = "(foo)"
    assert form_at(text, 0) == (0, 5)


def test_cursor_at_close_bracket_returns_form() -> None:
    """Cursor exactly on the closing bracket returns that form."""
    text = "(foo)"
    assert form_at(text, 4) == (0, 5)


def test_char_literal_paren_is_not_a_bracket() -> None:
    """``\\(`` is a character literal and must not count as an open paren."""
    text = "[\\( 1]"
    # 0:'[' 1:'\' 2:'(' 3:' ' 4:'1' 5:']'
    assert form_at(text, 4) == (0, 6)


def test_unbalanced_text_returns_none_gracefully() -> None:
    """Unbalanced input must not crash and returns ``None``."""
    text = "(defn foo [x"
    assert form_at(text, 5) is None
    assert top_level_form_at(text, 5) is None


def test_empty_text_returns_none() -> None:
    """Empty text never yields a form."""
    assert form_at("", 0) is None
    assert top_level_form_at("", 0) is None


def test_out_of_range_cursor_returns_none() -> None:
    """Negative or past-end positions yield ``None``."""
    text = "(foo)"
    assert form_at(text, -1) is None
    assert form_at(text, 100) is None


def test_mismatched_brackets_do_not_match() -> None:
    """Bracket-pair mismatch (``(]``) does not produce a false match."""
    text = "(]"
    assert form_at(text, 0) is None
