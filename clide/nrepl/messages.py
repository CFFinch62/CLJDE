"""Message builders for the nREPL protocol.

Every builder is a pure function that returns a plain ``dict`` ready to
be bencoded and dropped on the wire. Each message carries a short
random hex ``id`` (collision-unlikely enough for an interactive
session) so responses can be correlated. Op names use the nREPL
on-the-wire spelling (``ls-sessions``, ``load-file``).
"""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a fresh 8-character hex identifier."""
    return uuid.uuid4().hex[:8]


def build_clone(session: str | None = None) -> dict:
    """Build a ``clone`` request, optionally cloning from an existing session."""
    msg: dict = {"op": "clone", "id": new_id()}
    if session is not None:
        msg["session"] = session
    return msg


def build_close(session: str) -> dict:
    """Build a ``close`` request that terminates ``session`` on the server."""
    return {"op": "close", "id": new_id(), "session": session}


def build_describe() -> dict:
    """Build a ``describe`` request asking the server about supported ops."""
    return {"op": "describe", "id": new_id()}


def build_eval(
    code: str,
    session: str,
    ns: str | None = None,
    file: str | None = None,
    line: int | None = None,
    column: int | None = None,
) -> dict:
    """Build an ``eval`` request for ``code`` in ``session``.

    ``ns``, ``file``, ``line`` and ``column`` are optional source hints
    that middleware such as cider-nrepl uses to enrich stack traces and
    completions.
    """
    msg: dict = {
        "op": "eval",
        "id": new_id(),
        "session": session,
        "code": code,
    }
    if ns is not None:
        msg["ns"] = ns
    if file is not None:
        msg["file"] = file
    if line is not None:
        msg["line"] = int(line)
    if column is not None:
        msg["column"] = int(column)
    return msg


def build_interrupt(session: str, interrupt_id: str) -> dict:
    """Build an ``interrupt`` request targeting ``interrupt_id`` in ``session``."""
    return {
        "op": "interrupt",
        "id": new_id(),
        "session": session,
        "interrupt-id": interrupt_id,
    }


def build_load_file(
    file_contents: str,
    file_name: str,
    file_path: str,
    session: str,
) -> dict:
    """Build a ``load-file`` request uploading ``file_contents`` for evaluation.

    ``file_name`` is the bare file name (``core.clj``), ``file_path`` is
    either the absolute path or a project-relative path — nREPL uses it
    for source mapping in exception traces.
    """
    return {
        "op": "load-file",
        "id": new_id(),
        "session": session,
        "file": file_contents,
        "file-name": file_name,
        "file-path": file_path,
    }


def build_stdin(input: str, session: str) -> dict:
    """Build a ``stdin`` request delivering ``input`` to the evaluating form."""
    return {
        "op": "stdin",
        "id": new_id(),
        "session": session,
        "stdin": input,
    }


def build_ls_sessions() -> dict:
    """Build a ``ls-sessions`` request asking the server to list sessions."""
    return {"op": "ls-sessions", "id": new_id()}
