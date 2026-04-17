"""Clojure syntax highlighter for the CLIDE editor.

Implements a hand-written per-block scanner (rather than a regex sweep)
so multi-line strings and character literals can be handled correctly.
Block state is used to carry ``in-string`` across line boundaries.

Token classes recognised, all styled from :data:`clide.config.theme.DEFAULT_PALETTE`:
  * Special forms — amber bright, bold
  * Core functions — amber primary
  * Keywords (``:foo``, ``::foo``, ``:ns/foo``) — blue bright
  * Strings (with ``\\`` escape handling, multi-line) — success green
  * Line comments (``;`` to EOL) — foreground dim, italic
  * Form-skip marker (``#_``) — foreground dim, italic
  * Numbers — blue primary
  * Character literals (``\\a``, ``\\newline``) — success green
  * Metadata (``^:foo``, ``^String``, ``^{``) — blue primary, italic
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from clide.config.theme import DEFAULT_PALETTE

STATE_NORMAL = 0
STATE_IN_STRING = 1

_SYMBOL_EXTRA = set("*+!-_?./<>=&%$'")


def _is_symbol_start(c: str) -> bool:
    """Return True if ``c`` may begin a Clojure symbol token."""
    return c.isalpha() or c in _SYMBOL_EXTRA


def _is_symbol_char(c: str) -> bool:
    """Return True if ``c`` may continue a Clojure symbol token."""
    return c.isalnum() or c in _SYMBOL_EXTRA


SPECIAL_FORMS: frozenset[str] = frozenset({
    "def", "defn", "defn-", "defmacro", "let", "let*", "letfn",
    "if", "if-not", "if-let", "when", "when-not", "when-let",
    "fn", "fn*", "do", "loop", "recur", "quote", "var",
    "try", "catch", "finally", "throw",
    "cond", "condp", "case", "and", "or", "not",
    "ns", "in-ns", "require", "use", "import",
    "deref", "reify", "defrecord", "defprotocol", "defmulti", "defmethod",
    "extend", "extend-type", "extend-protocol",
    "for", "doseq", "dotimes", "while",
    "binding", "with-open", "with-meta",
    "set!", "new", ".", "..",
    "->", "->>", "as->", "some->", "some->>", "cond->", "cond->>",
    "comment",
})

CORE_FUNCTIONS: frozenset[str] = frozenset({
    "map", "mapv", "mapcat", "filter", "filterv", "reduce", "reductions",
    "apply", "first", "rest", "next", "nth", "last", "butlast",
    "cons", "conj", "into", "concat", "count", "range", "repeat", "repeatedly",
    "iterate", "cycle", "partition", "partition-all", "partition-by",
    "take", "take-while", "take-nth", "drop", "drop-while", "drop-last",
    "seq", "sequence", "lazy-seq", "doall", "dorun",
    "assoc", "assoc-in", "dissoc", "merge", "merge-with",
    "update", "update-in", "get", "get-in", "select-keys", "keys", "vals",
    "contains?", "keyword", "symbol", "name", "namespace",
    "str", "print", "println", "pr", "prn", "format", "printf",
    "type", "class", "instance?",
    "=", "==", "not=", "<", ">", "<=", ">=",
    "+", "-", "*", "/", "inc", "dec", "max", "min", "mod", "rem", "quot",
    "zero?", "pos?", "neg?", "odd?", "even?", "nil?", "empty?",
    "true?", "false?", "some?", "some", "every?", "not-any?",
    "sort", "sort-by", "group-by", "frequencies", "distinct", "reverse",
    "flatten", "keep", "remove", "interpose", "interleave", "zipmap",
    "comp", "partial", "juxt", "memoize", "constantly", "identity", "complement",
    "atom", "ref", "swap!", "reset!", "compare-and-set!", "deref", "dosync",
    "slurp", "spit", "read-string", "eval",
})


class ClojureHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Clojure source code."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._formats = _build_formats()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        """Apply formatting to a single logical text block (line)."""
        n = len(text)
        i = 0
        state = STATE_NORMAL if self.previousBlockState() < 0 else self.previousBlockState()

        if state == STATE_IN_STRING:
            end, finished = self._consume_string_body(text, 0)
            self.setFormat(0, end, self._formats["string"])
            i = end
            state = STATE_NORMAL if finished else STATE_IN_STRING
            if state == STATE_IN_STRING:
                self.setCurrentBlockState(STATE_IN_STRING)
                return

        while i < n:
            c = text[i]
            if c == ";":
                self.setFormat(i, n - i, self._formats["comment"])
                i = n
                break
            if c == "#" and i + 1 < n and text[i + 1] == "_":
                self.setFormat(i, 2, self._formats["comment"])
                i += 2
                continue
            if c == '"':
                start = i
                i += 1
                end, finished = self._consume_string_body(text, i)
                self.setFormat(start, end - start, self._formats["string"])
                i = end
                if not finished:
                    state = STATE_IN_STRING
                    break
                continue
            if c == "\\":
                i = self._paint_char_literal(text, i)
                continue
            if c == ":":
                i = self._paint_keyword(text, i)
                continue
            if c == "^":
                i = self._paint_metadata(text, i)
                continue
            if c.isdigit() or (c in "+-" and i + 1 < n and text[i + 1].isdigit()):
                i = self._paint_number(text, i)
                continue
            if _is_symbol_start(c):
                i = self._paint_symbol(text, i)
                continue
            i += 1

        self.setCurrentBlockState(state)

    # ---------------------------------------------------- token sub-scanners

    def _consume_string_body(self, text: str, start: int) -> tuple[int, bool]:
        """Scan a string body from ``start`` and return ``(end, finished)``."""
        n = len(text)
        i = start
        while i < n:
            ch = text[i]
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            i += 1
            if ch == '"':
                return i, True
        return n, False

    def _paint_char_literal(self, text: str, start: int) -> int:
        """Paint a character literal starting at ``start``; return next index."""
        n = len(text)
        i = start + 1
        if i < n:
            i += 1
            while i < n and text[i].isalpha():
                i += 1
        self.setFormat(start, i - start, self._formats["char"])
        return i

    def _paint_keyword(self, text: str, start: int) -> int:
        """Paint a ``:foo`` / ``::foo`` keyword; return next index."""
        n = len(text)
        i = start + 1
        if i < n and text[i] == ":":
            i += 1
        while i < n and _is_symbol_char(text[i]):
            i += 1
        self.setFormat(start, i - start, self._formats["keyword"])
        return i

    def _paint_metadata(self, text: str, start: int) -> int:
        """Paint a ``^`` metadata marker (plus any symbol/keyword body)."""
        n = len(text)
        i = start + 1
        if i < n and text[i] == ":":
            i += 1
            if i < n and text[i] == ":":
                i += 1
        while i < n and _is_symbol_char(text[i]):
            i += 1
        self.setFormat(start, i - start, self._formats["metadata"])
        return i

    def _paint_number(self, text: str, start: int) -> int:
        """Paint a numeric literal starting at ``start``; return next index."""
        n = len(text)
        i = start + 1
        while i < n and (text[i].isalnum() or text[i] in "./+-"):
            i += 1
        self.setFormat(start, i - start, self._formats["number"])
        return i

    def _paint_symbol(self, text: str, start: int) -> int:
        """Paint a symbol token; apply special/core formatting by word."""
        n = len(text)
        i = start + 1
        while i < n and _is_symbol_char(text[i]):
            i += 1
        word = text[start:i]
        if word in SPECIAL_FORMS:
            self.setFormat(start, i - start, self._formats["special"])
        elif word in CORE_FUNCTIONS:
            self.setFormat(start, i - start, self._formats["core"])
        return i


def _build_formats() -> dict[str, QTextCharFormat]:
    """Build the ``QTextCharFormat`` table from the default palette."""
    p = DEFAULT_PALETTE
    formats: dict[str, QTextCharFormat] = {}

    special = QTextCharFormat()
    special.setForeground(QColor(p.amber_bright))
    special.setFontWeight(QFont.Weight.Bold)
    formats["special"] = special

    core = QTextCharFormat()
    core.setForeground(QColor(p.amber_primary))
    formats["core"] = core

    keyword = QTextCharFormat()
    keyword.setForeground(QColor(p.blue_bright))
    formats["keyword"] = keyword

    string = QTextCharFormat()
    string.setForeground(QColor(p.success_green))
    formats["string"] = string

    comment = QTextCharFormat()
    comment.setForeground(QColor(p.foreground_dim))
    comment.setFontItalic(True)
    formats["comment"] = comment

    number = QTextCharFormat()
    number.setForeground(QColor(p.blue_primary))
    formats["number"] = number

    char = QTextCharFormat()
    char.setForeground(QColor(p.success_green))
    formats["char"] = char

    metadata = QTextCharFormat()
    metadata.setForeground(QColor(p.blue_primary))
    metadata.setFontItalic(True)
    formats["metadata"] = metadata

    return formats
