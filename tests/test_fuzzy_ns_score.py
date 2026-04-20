"""Tests for :func:`clide.ui.fuzzy_ns_dialog.fuzzy_score`.

The scoring is a subsequence match with a streak bonus. These tests
verify the rejection path, empty-query behaviour, and the ordering that
the dialog relies on to keep `str` -> `clojure.string` near the top.
"""

from __future__ import annotations

from clide.ui.fuzzy_ns_dialog import fuzzy_score


def test_empty_query_scores_zero() -> None:
    """An empty query matches anything with a score of ``0``."""
    assert fuzzy_score("", "clojure.core") == 0


def test_non_subsequence_returns_none() -> None:
    """Characters not present in order yield ``None``."""
    assert fuzzy_score("xyz", "clojure.core") is None


def test_consecutive_match_outranks_scattered_match() -> None:
    """A run of consecutive matches beats scattered hits of the same length."""
    consecutive = fuzzy_score("str", "clojure.string")
    scattered = fuzzy_score("str", "clojure.set-transient-reducer")
    assert consecutive is not None and scattered is not None
    assert consecutive > scattered


def test_case_insensitive() -> None:
    """Scoring ignores case differences."""
    lower = fuzzy_score("str", "clojure.string")
    upper = fuzzy_score("STR", "Clojure.String")
    assert lower == upper


def test_exact_prefix_scores_highest_among_candidates() -> None:
    """Among a set of candidates the exact prefix ranks first."""
    names = ["clojure.set", "clojure.string", "clojure.core"]
    scores = [(fuzzy_score("str", n), n) for n in names]
    scores = [(s, n) for s, n in scores if s is not None]
    scores.sort(key=lambda pair: -pair[0])
    assert scores[0][1] == "clojure.string"
