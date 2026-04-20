"""Tests for :mod:`cljde.nrepl.messages`.

Each builder is a pure function, so the tests focus on three things:
the correct ``op`` string, the presence of required keys, and a
well-formed ``id`` that survives bencode round-tripping.
"""

from __future__ import annotations

import string

import pytest

from cljde.nrepl import bencode, messages


_HEX = set(string.hexdigits.lower())


def _assert_valid_id(msg: dict) -> None:
    msg_id = msg["id"]
    assert isinstance(msg_id, str)
    assert len(msg_id) == 8
    assert set(msg_id).issubset(_HEX)


def test_new_id_is_short_hex_and_unique() -> None:
    """``new_id`` produces 8 hex chars and doesn't repeat trivially."""
    ids = {messages.new_id() for _ in range(200)}
    assert len(ids) == 200
    for ident in ids:
        assert len(ident) == 8
        assert set(ident).issubset(_HEX)


def test_build_clone_without_parent() -> None:
    """``build_clone()`` with no parent omits the ``session`` key."""
    msg = messages.build_clone()
    assert msg["op"] == "clone"
    assert "session" not in msg
    _assert_valid_id(msg)


def test_build_clone_with_parent_session() -> None:
    """Passing a parent session puts it under the ``session`` key."""
    msg = messages.build_clone("abc123")
    assert msg == {"op": "clone", "id": msg["id"], "session": "abc123"}
    _assert_valid_id(msg)


def test_build_close() -> None:
    """``build_close`` carries the target session id."""
    msg = messages.build_close("s1")
    assert msg["op"] == "close"
    assert msg["session"] == "s1"
    _assert_valid_id(msg)


def test_build_describe() -> None:
    """``build_describe`` carries no session or extras."""
    msg = messages.build_describe()
    assert msg["op"] == "describe"
    assert set(msg) == {"op", "id"}
    _assert_valid_id(msg)


def test_build_eval_minimal() -> None:
    """Minimal eval requires only ``code`` and ``session``."""
    msg = messages.build_eval("(+ 1 2)", "sess")
    assert msg["op"] == "eval"
    assert msg["session"] == "sess"
    assert msg["code"] == "(+ 1 2)"
    assert "ns" not in msg and "file" not in msg
    _assert_valid_id(msg)


def test_build_eval_with_source_hints() -> None:
    """Source hints are copied through verbatim."""
    msg = messages.build_eval(
        "(inc x)", "sess", ns="user", file="src.clj", line=7, column=3,
    )
    assert msg["ns"] == "user"
    assert msg["file"] == "src.clj"
    assert msg["line"] == 7
    assert msg["column"] == 3


def test_build_interrupt() -> None:
    """``build_interrupt`` names the eval it's trying to cancel."""
    msg = messages.build_interrupt("sess", "eval-42")
    assert msg["op"] == "interrupt"
    assert msg["session"] == "sess"
    assert msg["interrupt-id"] == "eval-42"
    _assert_valid_id(msg)


def test_build_load_file() -> None:
    """``build_load_file`` uses nREPL's dash-delimited key names."""
    msg = messages.build_load_file(
        file_contents="(ns foo) (defn bar [])",
        file_name="foo.clj",
        file_path="/tmp/foo.clj",
        session="sess",
    )
    assert msg["op"] == "load-file"
    assert msg["file"] == "(ns foo) (defn bar [])"
    assert msg["file-name"] == "foo.clj"
    assert msg["file-path"] == "/tmp/foo.clj"
    assert msg["session"] == "sess"
    _assert_valid_id(msg)


def test_build_stdin() -> None:
    """``build_stdin`` carries a single ``stdin`` payload."""
    msg = messages.build_stdin("line\n", "sess")
    assert msg["op"] == "stdin"
    assert msg["stdin"] == "line\n"
    assert msg["session"] == "sess"
    _assert_valid_id(msg)


def test_build_ls_sessions() -> None:
    """``build_ls_sessions`` carries only ``op`` and ``id``."""
    msg = messages.build_ls_sessions()
    assert msg["op"] == "ls-sessions"
    assert set(msg) == {"op", "id"}
    _assert_valid_id(msg)


@pytest.mark.parametrize("builder,args", [
    (messages.build_clone, ()),
    (messages.build_close, ("s",)),
    (messages.build_describe, ()),
    (messages.build_interrupt, ("s", "e")),
    (messages.build_stdin, ("x", "s")),
    (messages.build_ls_sessions, ()),
])
def test_every_message_roundtrips_through_bencode(builder, args) -> None:
    """Every builder produces a dict that survives bencode round-tripping."""
    msg = builder(*args)
    decoded, leftover = bencode.decode(bencode.encode(msg))
    assert leftover == b""
    assert decoded == msg


def test_eval_roundtrips_through_bencode() -> None:
    """``build_eval`` with hints survives bencode round-tripping."""
    msg = messages.build_eval("(+ 1 2)", "sess", ns="user", line=1, column=1)
    decoded, leftover = bencode.decode(bencode.encode(msg))
    assert leftover == b""
    assert decoded == msg


def test_load_file_roundtrips_through_bencode() -> None:
    """``build_load_file`` survives bencode round-tripping."""
    msg = messages.build_load_file("(ns a)", "a.clj", "/tmp/a.clj", "sess")
    decoded, leftover = bencode.decode(bencode.encode(msg))
    assert leftover == b""
    assert decoded == msg
