"""Composite REPL panel: status strip + output view + input line.

Holds references to a :class:`clide.nrepl.NreplClient` and a
:class:`clide.nrepl.SessionManager`, subscribes to client signals, and
dispatches user input as ``eval`` / ``load-file`` messages. Response
routing inspects each incoming dict for the nREPL payload keys
(``value``, ``out``, ``err``, ``ex``, ``ns``, ``status``, ``root-ex``)
and forwards them to the correct :class:`OutputView` append method.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clide.config.theme import DEFAULT_PALETTE
from clide.nrepl import messages
from clide.nrepl.client import NreplClient
from clide.nrepl.session import SessionManager
from clide.repl.input_line import InputLine
from clide.repl.output_view import OutputView

if TYPE_CHECKING:
    from clide.config.settings import Settings

log = logging.getLogger(__name__)

LED_SIZE_PX = 12


class ReplPane(QWidget):
    """Docked REPL panel: status strip, output transcript, input prompt."""

    connection_message_signal = pyqtSignal(str)
    ns_changed_signal = pyqtSignal(str)

    def __init__(
        self,
        client: NreplClient,
        sessions: SessionManager,
        settings: "Settings | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._sessions = sessions
        self._settings = settings
        self._endpoint: tuple[str, int] | None = None
        self._pending: dict[str, dict[str, object]] = {}
        self._last_ns: str = "user"

        self._build_ui()
        self._wire_signals()
        self._refresh_status_strip()

    # ------------------------------------------------------------ public API

    def output_view(self) -> OutputView:
        """Return the underlying :class:`OutputView` for direct appends."""
        return self._output

    def input_line(self) -> InputLine:
        """Return the :class:`InputLine` so callers can steal focus."""
        return self._input

    def client(self) -> NreplClient:
        """Return the shared nREPL client driving this pane."""
        return self._client

    def current_ns(self) -> str:
        """Return the namespace currently tracked for the default session."""
        session_id = self._client.default_session()
        if session_id is None:
            return "user"
        return self._sessions.get_current_ns(session_id)

    def endpoint(self) -> tuple[str, int] | None:
        """Return the last requested ``(host, port)`` or ``None``."""
        return self._endpoint

    def connect_to(self, host: str, port: int) -> None:
        """Initiate an external nREPL connection to ``host``:``port``."""
        self._endpoint = (host, port)
        self._output.append_info(f"Connecting to nrepl://{host}:{port} ...")
        self._client.connect(host, port)

    def disconnect(self) -> None:
        """Ask the client to close its connection."""
        if self._client.state() == "disconnected":
            return
        self._output.append_info("Disconnecting ...")
        self._client.disconnect()

    def eval(
        self,
        code: str,
        ns: str | None = None,
        file: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        """Send ``code`` for evaluation in the default session."""
        session_id = self._client.default_session()
        if not self._client.is_connected() or session_id is None:
            self._output.append_info("Not connected; eval ignored.")
            return
        eval_ns = ns or self.current_ns()
        self._output.append_command(code, eval_ns)
        msg = messages.build_eval(
            code=code, session=session_id, ns=eval_ns,
            file=file, line=line, column=column,
        )
        self._pending[msg["id"]] = {"code": code, "ns": eval_ns, "file": file}
        self._sessions.track_eval(
            session_id, msg["id"], code,
            source_location={"file": file, "line": line, "column": column},
        )
        self._client.send(msg)

    def load_file(self, file_contents: str, file_name: str, file_path: str) -> None:
        """Send a ``load-file`` request for the supplied buffer."""
        session_id = self._client.default_session()
        if not self._client.is_connected() or session_id is None:
            self._output.append_info("Not connected; load-file ignored.")
            return
        self._output.append_command(
            f"(load-file \"{file_path}\")", self.current_ns(),
        )
        msg = messages.build_load_file(
            file_contents=file_contents, file_name=file_name,
            file_path=file_path, session=session_id,
        )
        self._pending[msg["id"]] = {"code": file_contents, "file": file_path}
        self._sessions.track_eval(session_id, msg["id"], f"load-file {file_name}")
        self._client.send(msg)

    def interrupt(self) -> None:
        """Request interruption of every pending eval on the default session."""
        session_id = self._client.default_session()
        if session_id is None:
            return
        for msg_id in self._sessions.pending_eval_ids(session_id):
            self._client.send(messages.build_interrupt(session_id, msg_id))

    # ---------------------------------------------------------- UI plumbing

    def _build_ui(self) -> None:
        """Assemble the vertical layout: status strip, output, input line."""
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        root.addLayout(self._build_status_strip())

        self._output = OutputView(self._settings, self)
        root.addWidget(self._output, 1)

        self._input = InputLine(self._settings, self)
        root.addWidget(self._input, 0)

    def _build_status_strip(self) -> QHBoxLayout:
        """Build the top strip: LED, namespace, session, Clear button."""
        strip = QHBoxLayout()
        strip.setContentsMargins(0, 0, 0, 0)
        strip.setSpacing(8)

        self._led = QFrame(self)
        self._led.setObjectName("replLed")
        self._led.setFixedSize(LED_SIZE_PX, LED_SIZE_PX)
        self._paint_led(DEFAULT_PALETTE.foreground_dim)
        strip.addWidget(self._led, 0, Qt.AlignmentFlag.AlignVCenter)

        self._ns_label = QLabel("ns: —", self)
        self._ns_label.setObjectName("replNsLabel")
        strip.addWidget(self._ns_label, 0)

        self._session_label = QLabel("session: —", self)
        self._session_label.setObjectName("replSessionLabel")
        strip.addWidget(self._session_label, 0)

        strip.addStretch(1)

        self._clear_btn = QPushButton("Clear", self)
        self._clear_btn.setObjectName("replClearButton")
        self._clear_btn.setFlat(True)
        strip.addWidget(self._clear_btn, 0)

        return strip

    def _wire_signals(self) -> None:
        """Hook client signals and the input line into local slots."""
        self._client.connection_state_signal.connect(self._on_state)
        self._client.session_cloned_signal.connect(self._on_session)
        self._client.response_signal.connect(self._on_response)
        self._input.submit_signal.connect(self._on_submit)
        self._clear_btn.clicked.connect(self._output.clear)

    # ----------------------------------------------------- signal handlers

    def _on_submit(self, code: str) -> None:
        """Handle user-submitted input from the prompt."""
        self.eval(code)

    def _on_state(self, state: str) -> None:
        """React to connection-state transitions from the client."""
        if state == "connected":
            endpoint = self._endpoint
            suffix = f" ({endpoint[0]}:{endpoint[1]})" if endpoint else ""
            self._output.append_info(f"Connected{suffix}")
            self._paint_led(DEFAULT_PALETTE.success_green)
        elif state == "connecting":
            self._paint_led(DEFAULT_PALETTE.amber_primary)
        elif state == "error":
            self._output.append_info("Connection error.")
            self._paint_led(DEFAULT_PALETTE.error_red)
        else:
            self._output.append_info("Disconnected.")
            self._paint_led(DEFAULT_PALETTE.foreground_dim)
            self._sessions_forget_default()
        self._refresh_status_strip()

    def _on_session(self, session_id: str) -> None:
        """Register the cloned session so namespace tracking works."""
        self._sessions.track_session(session_id)
        self._refresh_status_strip()

    def _on_response(self, msg_id: str, response: dict) -> None:
        """Route an incoming nREPL response to the output view."""
        session_id = response.get("session") or self._client.default_session()

        ns = response.get("ns")
        if isinstance(ns, str) and ns and session_id:
            self._sessions.update_ns_from_response(session_id, response)
            self._refresh_status_strip()

        if "value" in response:
            value = response.get("value")
            self._output.append_value(
                str(value) if value is not None else "nil",
                ns if isinstance(ns, str) else self.current_ns(),
            )

        out = response.get("out")
        if isinstance(out, str) and out:
            self._output.append_stdout(out)

        err = response.get("err")
        if isinstance(err, str) and err:
            self._output.append_stderr(err)

        ex = response.get("ex")
        if isinstance(ex, str) and ex:
            root_ex = response.get("root-ex")
            message = root_ex if isinstance(root_ex, str) and root_ex != ex else ""
            self._output.append_exception(ex, message, "")

        status = response.get("status")
        if isinstance(status, list) and session_id:
            if "interrupted" in status:
                self._output.append_info("Interrupted.")
            if "done" in status:
                self._sessions.complete_eval(session_id, msg_id)
                self._pending.pop(msg_id, None)

    # --------------------------------------------------------- presentation

    def _refresh_status_strip(self) -> None:
        """Keep the ns/session labels in sync with the current state."""
        session_id = self._client.default_session()
        if session_id is None:
            self._ns_label.setText("ns: —")
            self._session_label.setText("session: —")
            return
        ns = self._sessions.get_current_ns(session_id)
        self._ns_label.setText(f"ns: {ns}")
        self._session_label.setText(f"session: {session_id[:8]}")
        if ns != self._last_ns:
            self._last_ns = ns
            self.ns_changed_signal.emit(ns)

    def _paint_led(self, colour_hex: str) -> None:
        """Update the connection-status LED to ``colour_hex``."""
        radius = LED_SIZE_PX // 2
        self._led.setStyleSheet(
            f"background-color: {colour_hex}; "
            f"border-radius: {radius}px; "
            f"border: 1px solid {DEFAULT_PALETTE.background_light};"
        )

    def _sessions_forget_default(self) -> None:
        """Drop the default session record on disconnect."""
        session_id = self._client.default_session()
        if session_id is not None:
            self._sessions.forget_session(session_id)
