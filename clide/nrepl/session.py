"""Bookkeeping for nREPL sessions and their in-flight evaluations.

An nREPL server can host multiple sessions, each with its own
namespace and bindings. :class:`Session` holds per-session state;
:class:`SessionManager` owns a collection of them and watches incoming
responses for namespace switches and eval completion. Pure Python —
no Qt imports — so the module can be exercised in isolation from UI
tests.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

_HISTORY_CAP = 1000


@dataclass
class Session:
    """Per-session state tracked on the client side."""

    session_id: str
    current_ns: str = "user"
    pending_evals: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalRecord:
    """A completed evaluation kept in the history ring."""

    session_id: str
    msg_id: str
    code: str
    source_location: dict[str, Any] | None
    started_at: float
    finished_at: float


class SessionManager:
    """Coordinates known sessions and their pending/completed evals."""

    def __init__(self, history_cap: int = _HISTORY_CAP) -> None:
        self._sessions: dict[str, Session] = {}
        self._history: deque[EvalRecord] = deque(maxlen=history_cap)

    # ----------------------------------------------------- session registry

    def track_session(self, session_id: str) -> Session:
        """Register ``session_id`` and return its :class:`Session` record.

        Idempotent: re-calling with a known id returns the existing
        record without clobbering its ``current_ns`` or pending evals.
        """
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        log.debug("SessionManager: tracking session %s", session_id)
        return session

    def forget_session(self, session_id: str) -> None:
        """Drop ``session_id`` from the registry (e.g. after ``close``)."""
        if self._sessions.pop(session_id, None) is not None:
            log.debug("SessionManager: forgot session %s", session_id)

    def has_session(self, session_id: str) -> bool:
        """Return True if ``session_id`` is currently registered."""
        return session_id in self._sessions

    def sessions(self) -> list[str]:
        """Return the list of currently-tracked session ids."""
        return list(self._sessions)

    def get_current_ns(self, session_id: str) -> str:
        """Return the current namespace for ``session_id`` (``user`` by default)."""
        session = self._sessions.get(session_id)
        return session.current_ns if session is not None else "user"

    # ---------------------------------------------------- response handlers

    def update_ns_from_response(self, session_id: str, response: dict) -> None:
        """Update the tracked namespace if ``response`` reports a new ``ns``."""
        ns = response.get("ns")
        if not isinstance(ns, str) or not ns:
            return
        session = self._sessions.get(session_id)
        if session is None:
            log.debug("ns update for unknown session %s ignored", session_id)
            return
        if session.current_ns != ns:
            log.debug("session %s ns: %s -> %s", session_id, session.current_ns, ns)
            session.current_ns = ns

    # ------------------------------------------------------- eval tracking

    def track_eval(
        self,
        session_id: str,
        msg_id: str,
        code: str,
        source_location: dict[str, Any] | None = None,
    ) -> None:
        """Record ``msg_id`` as a pending eval on ``session_id``."""
        session = self.track_session(session_id)
        session.pending_evals[msg_id] = {
            "code": code,
            "source_location": source_location,
            "started_at": time.monotonic(),
        }

    def complete_eval(self, session_id: str, msg_id: str) -> EvalRecord | None:
        """Mark the eval ``msg_id`` as complete; return its :class:`EvalRecord`.

        Returns ``None`` if the eval was not being tracked (e.g. the
        session has already been forgotten).
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        meta = session.pending_evals.pop(msg_id, None)
        if meta is None:
            return None
        record = EvalRecord(
            session_id=session_id,
            msg_id=msg_id,
            code=meta["code"],
            source_location=meta.get("source_location"),
            started_at=meta["started_at"],
            finished_at=time.monotonic(),
        )
        self._history.append(record)
        return record

    def pending_eval_ids(self, session_id: str) -> list[str]:
        """Return the message ids of evals still in flight for ``session_id``."""
        session = self._sessions.get(session_id)
        return list(session.pending_evals) if session is not None else []

    def history(self) -> list[EvalRecord]:
        """Return a snapshot of completed evals, oldest first."""
        return list(self._history)

    def clear_history(self) -> None:
        """Drop all completed-eval records."""
        self._history.clear()
