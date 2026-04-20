"""QThread-based TCP worker for the nREPL client.

Owns the socket exclusively. The run loop alternates between draining
an outbound :class:`queue.Queue` of pre-bencoded frames and reading
whatever is available on the socket, decoding complete bencode values
via :mod:`cljde.nrepl.bencode` and emitting them as Qt signals. Short
``settimeout`` intervals give the loop a chance to notice the stop
flag and any newly enqueued outbound bytes.

Only :meth:`send_bytes` and :meth:`stop` are safe to call from other
threads; everything else runs on the worker thread.
"""

from __future__ import annotations

import logging
import queue
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from cljde.nrepl import bencode

log = logging.getLogger(__name__)

_RECV_BUFSIZE = 8192
_POLL_INTERVAL = 0.1
_CONNECT_TIMEOUT = 5.0


class SocketWorker(QThread):
    """Background TCP/bencode pump for an nREPL connection."""

    message_received_signal = pyqtSignal(dict)
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self._host = host
        self._port = int(port)
        self._outbound: queue.Queue[bytes] = queue.Queue()
        self._stop_requested = False
        self._socket: socket.socket | None = None

    # -------------------------------------------------------- cross-thread API

    def send_bytes(self, data: bytes) -> None:
        """Enqueue ``data`` for delivery by the worker thread."""
        if not data:
            return
        self._outbound.put(data)

    def stop(self) -> None:
        """Request a graceful shutdown of the read loop."""
        self._stop_requested = True

    # ----------------------------------------------------------- thread entry

    def run(self) -> None:  # noqa: D401 — QThread convention
        """Main worker loop; do not call directly."""
        try:
            self._socket = socket.create_connection(
                (self._host, self._port), timeout=_CONNECT_TIMEOUT,
            )
            self._socket.settimeout(_POLL_INTERVAL)
        except (OSError, ValueError) as exc:
            self.error_signal.emit(f"connect failed: {exc}")
            return

        self.connected_signal.emit()
        reason = self._read_loop(self._socket)
        self._close_socket()
        self.disconnected_signal.emit(reason)

    # ------------------------------------------------------------ read loop

    def _read_loop(self, sock: socket.socket) -> str:
        buffer = bytearray()
        while not self._stop_requested:
            if not self._drain_outbound(sock):
                return "send failed"
            try:
                chunk = sock.recv(_RECV_BUFSIZE)
            except socket.timeout:
                continue
            except OSError as exc:
                self.error_signal.emit(f"recv failed: {exc}")
                return f"recv failed: {exc}"
            if not chunk:
                return "peer closed connection"
            buffer.extend(chunk)
            if not self._drain_buffer(buffer):
                return "bencode error"
        return "stopped by client"

    def _drain_outbound(self, sock: socket.socket) -> bool:
        while True:
            try:
                data = self._outbound.get_nowait()
            except queue.Empty:
                return True
            try:
                sock.sendall(data)
            except OSError as exc:
                self.error_signal.emit(f"send failed: {exc}")
                return False

    def _drain_buffer(self, buffer: bytearray) -> bool:
        try:
            values, leftover = bencode.decode_all(bytes(buffer))
        except bencode.BencodeError as exc:
            self.error_signal.emit(f"bencode error: {exc}")
            return False
        buffer.clear()
        buffer.extend(leftover)
        for value in values:
            if isinstance(value, dict):
                self.message_received_signal.emit(value)
            else:
                log.warning("dropping non-dict nREPL frame: %r", value)
        return True

    # ----------------------------------------------------------- teardown

    def _close_socket(self) -> None:
        sock = self._socket
        self._socket = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError as exc:
            log.debug("socket close raised: %s", exc)

    # --------------------------------------------------------- introspection

    def connection_target(self) -> tuple[str, int]:
        """Return the ``(host, port)`` tuple this worker is bound to."""
        return self._host, self._port

    def pending_outbound(self) -> int:
        """Return a best-effort count of queued outbound frames."""
        return self._outbound.qsize()

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return f"<SocketWorker {self._host}:{self._port}>"
