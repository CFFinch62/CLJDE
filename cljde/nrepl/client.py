"""High-level nREPL client exposed as a :class:`QObject`.

Wraps a :class:`SocketWorker`, drives the initial ``clone`` handshake,
tracks pending message ids, and forwards every response as a
:attr:`response_signal`. Consumers (the REPL UI in Phase 5) should
treat this class as the one-stop entry point: call :meth:`connect`,
watch :attr:`connection_state_signal` and :attr:`session_cloned_signal`
for lifecycle events, and :meth:`send` message dicts built with
:mod:`cljde.nrepl.messages`.

Thread model: the :class:`SocketWorker` owns the socket on its own
thread; this object lives on the thread that constructed it (normally
the GUI thread). Worker signals are queued across the thread boundary
by Qt's default connection type, so handler bodies always run where
this object lives.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from cljde.nrepl import bencode, messages
from cljde.nrepl.socket_worker import SocketWorker

log = logging.getLogger(__name__)

ConnectionState = str  # "connecting" | "connected" | "disconnected" | "error"


class NreplClient(QObject):
    """Qt-signal facade over an nREPL TCP connection."""

    response_signal = pyqtSignal(str, dict)
    connection_state_signal = pyqtSignal(str)
    session_cloned_signal = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: SocketWorker | None = None
        self._state: ConnectionState = "disconnected"
        self._default_session: str | None = None
        self._pending: dict[str, dict[str, Any]] = {}
        self._clone_id: str | None = None

    # ---------------------------------------------------------- public API

    def connect(self, host: str, port: int) -> None:
        """Start the socket worker and kick off the clone handshake.

        No-op if the client is already connecting or connected.
        """
        if self._worker is not None:
            log.debug("connect() ignored; worker already running")
            return
        self._default_session = None
        self._pending.clear()
        self._clone_id = None

        worker = SocketWorker(host, port)
        worker.connected_signal.connect(
            self._on_worker_connected, Qt.ConnectionType.QueuedConnection,
        )
        worker.disconnected_signal.connect(
            self._on_worker_disconnected, Qt.ConnectionType.QueuedConnection,
        )
        worker.error_signal.connect(
            self._on_worker_error, Qt.ConnectionType.QueuedConnection,
        )
        worker.message_received_signal.connect(
            self._on_worker_message, Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(self._on_worker_finished)

        self._worker = worker
        self._set_state("connecting")
        worker.start()

    def disconnect(self) -> None:
        """Request a graceful shutdown of the connection."""
        worker = self._worker
        if worker is None:
            return
        worker.stop()

    def send(self, message: dict) -> str:
        """Encode and enqueue ``message``; return its ``id``."""
        if self._worker is None:
            raise RuntimeError("cannot send: nREPL client is not connected")
        msg_id = message.get("id")
        if not isinstance(msg_id, str) or not msg_id:
            raise ValueError("message must include a non-empty 'id' string")
        self._pending[msg_id] = {
            "op": message.get("op"),
            "session": message.get("session"),
        }
        self._worker.send_bytes(bencode.encode(message))
        return msg_id

    def is_connected(self) -> bool:
        """Return True once the clone handshake has completed."""
        return self._state == "connected"

    def default_session(self) -> str | None:
        """Return the session id obtained from the initial clone, if any."""
        return self._default_session

    def state(self) -> ConnectionState:
        """Return the last broadcast connection state."""
        return self._state

    # ---------------------------------------------------- worker callbacks

    def _on_worker_connected(self) -> None:
        log.info("nREPL socket connected; sending clone")
        clone_msg = messages.build_clone()
        self._clone_id = clone_msg["id"]
        self._pending[self._clone_id] = {"op": "clone", "session": None}
        assert self._worker is not None  # established by connect()
        self._worker.send_bytes(bencode.encode(clone_msg))

    def _on_worker_disconnected(self, reason: str) -> None:
        log.info("nREPL socket disconnected: %s", reason)
        self._set_state("disconnected")

    def _on_worker_error(self, reason: str) -> None:
        log.warning("nREPL socket error: %s", reason)
        self._set_state("error")

    def _on_worker_message(self, response: dict) -> None:
        msg_id = response.get("id")
        if not isinstance(msg_id, str):
            log.debug("dropping nREPL frame without id: %r", response)
            return

        if msg_id == self._clone_id:
            self._handle_clone_response(response)

        self.response_signal.emit(msg_id, response)

        status = response.get("status")
        if isinstance(status, list) and "done" in status:
            self._pending.pop(msg_id, None)

    def _on_worker_finished(self) -> None:
        log.debug("SocketWorker QThread finished; releasing reference")
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------- internals

    def _handle_clone_response(self, response: dict) -> None:
        new_session = response.get("new-session")
        if isinstance(new_session, str) and new_session:
            self._default_session = new_session
            log.info("nREPL default session cloned: %s", new_session)
            self._set_state("connected")
            self.session_cloned_signal.emit(new_session)

    def _set_state(self, state: ConnectionState) -> None:
        if state == self._state:
            return
        self._state = state
        self.connection_state_signal.emit(state)
