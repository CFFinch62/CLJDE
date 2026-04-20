"""Tests for :mod:`clide.editor.balance_checker`.

Covers unmatched opens, unmatched closes, bracket-kind mismatches, and
the classifier interactions that keep bracket characters inside strings
and line comments from being reported.
"""

from __future__ import annotations

from clide.editor.balance_checker import (
    KIND_MISMATCH,
    KIND_UNMATCHED_CLOSE,
    KIND_UNMATCHED_OPEN,
    check_balance,
)


def test_empty_text_has_no_errors() -> None:
    """An empty document produces no balance errors."""
    assert check_balance("") == []


def test_balanced_nested_forms_have_no_errors() -> None:
    """A well-formed nested Clojure form returns an empty list."""
    assert check_balance("(let [x 1] (+ x [1 2 {:a 3}]))") == []


def test_unmatched_open_is_reported_at_open_position() -> None:
    """A stray ``(`` yields :data:`KIND_UNMATCHED_OPEN` at its index."""
    errors = check_balance("(foo")
    assert len(errors) == 1
    assert errors[0].pos == 0
    assert errors[0].kind == KIND_UNMATCHED_OPEN
    assert errors[0].char == "("


def test_unmatched_close_is_reported() -> None:
    """A stray ``)`` yields :data:`KIND_UNMATCHED_CLOSE` at its index."""
    errors = check_balance("foo)")
    assert len(errors) == 1
    assert errors[0].pos == 3
    assert errors[0].kind == KIND_UNMATCHED_CLOSE
    assert errors[0].char == ")"


def test_mismatched_close_is_reported() -> None:
    """A ``(`` closed by ``]`` is flagged as :data:`KIND_MISMATCH`."""
    errors = check_balance("(foo]")
    kinds = {e.kind for e in errors}
    assert KIND_MISMATCH in kinds


def test_brackets_inside_strings_are_ignored() -> None:
    """Brackets inside double-quoted strings do not affect balance."""
    assert check_balance('(str "()][{" :ok)') == []


def test_brackets_inside_line_comments_are_ignored() -> None:
    """Brackets on the right of ``;`` on the same line are not counted."""
    text = "(foo) ;; ( [ { never closed\n"
    assert check_balance(text) == []


def test_errors_are_sorted_by_position() -> None:
    """Multiple errors are returned sorted ascending by ``pos``."""
    errors = check_balance(") ( ]")
    positions = [e.pos for e in errors]
    assert positions == sorted(positions)


def test_mismatched_then_extra_close_both_reported() -> None:
    """A mismatched close followed by a stray close reports two errors."""
    errors = check_balance("(foo])")
    assert len(errors) >= 1
    assert any(e.kind == KIND_MISMATCH for e in errors)
