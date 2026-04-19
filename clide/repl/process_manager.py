"""Spawn and supervise an nREPL server process for the active project.

:class:`ReplProcessManager` wraps :class:`QProcess` so the rest of the
UI can treat REPL lifecycle as a small set of Qt signals:
``process_state_signal``, ``port_detected_signal``,
``output_line_signal`` and ``error_signal``. It selects the command
from :class:`Settings` based on the project type, streams stdout and
stderr one line at a time through a :class:`PortDetector`, and
distinguishes an expected stop from a crash via a single bookkeeping
flag.

Thread model: :class:`QProcess` runs the child on its own OS process
but reports back via Qt signals on the thread that owns the object
(the GUI thread), so slots mutate state without extra locks.
"""

from __future__ import annotations

import logging
import shlex
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from clide.repl.port_detector import PortDetector

if TYPE_CHECKING:
    from clide.config.settings import Settings
    from clide.files.project import Project

log = logging.getLogger(__name__)

ProcessState = str  # "idle" | "starting" | "running" | "crashed" | "stopping" | "stopped"

_TERMINATE_FALLBACK_MS = 500


class ReplProcessManager(QObject):
    """Lifecycle supervisor for an external nREPL server process."""

    process_state_signal = pyqtSignal(str)
    port_detected_signal = pyqtSignal(int)
    output_line_signal = pyqtSignal(str, str)
    error_signal = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._proc: QProcess | None = None
        self._detector = PortDetector()
        self._state: ProcessState = "idle"
        self._port: int | None = None
        self._project: "Project | None" = None
        self._stdout_buf: str = ""
        self._stderr_buf: str = ""
        self._expecting_stop: bool = False

    # ---------------------------------------------------------- public API

    def is_running(self) -> bool:
        """Return True while the child process is spawned and has not exited."""
        return self._state in ("starting", "running", "stopping")

    def state(self) -> ProcessState:
        """Return the last broadcast process state."""
        return self._state

    def current_port(self) -> int | None:
        """Return the port parsed from the child's startup output, if any."""
        return self._port

    def current_project(self) -> "Project | None":
        """Return the project the current (or most recent) process is tied to."""
        return self._project

    def start(self, project: "Project", settings: "Settings") -> None:
        """Spawn an nREPL server for ``project`` using ``settings`` commands."""
        if self.is_running():
            self.error_signal.emit("REPL process already running; stop it first.")
            return
        parts = self._command_for(project, settings)
        if parts is None:
            return

        self._project = project
        self._port = None
        self._detector.reset()
        self._stdout_buf = ""
        self._stderr_buf = ""
        self._expecting_stop = False

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.setWorkingDirectory(str(project.root))
        proc.readyReadStandardOutput.connect(self._on_ready_stdout)
        proc.readyReadStandardError.connect(self._on_ready_stderr)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_errored)
        self._proc = proc

        self._emit_state("starting")
        log.info("starting nREPL: %s (cwd=%s)", parts, project.root)
        proc.start(parts[0], parts[1:])

    def stop(self, timeout_ms: int = 3000) -> None:
        """Terminate the child, escalating to ``kill`` after ``timeout_ms``."""
        proc = self._proc
        if proc is None or self._state in ("idle", "stopped", "crashed"):
            return
        self._expecting_stop = True
        self._emit_state("stopping")
        log.info("stopping nREPL process (pid=%s)", proc.processId())
        proc.terminate()
        if not proc.waitForFinished(timeout_ms):
            log.warning("nREPL did not exit within %d ms; killing.", timeout_ms)
            proc.kill()
            proc.waitForFinished(_TERMINATE_FALLBACK_MS)

    def restart(self, project: "Project", settings: "Settings") -> None:
        """Stop the current process (if any) and start a fresh one."""
        if self.is_running():
            self.stop()
        self.start(project, settings)

    # --------------------------------------------------------- command build

    def _command_for(
        self, project: "Project", settings: "Settings",
    ) -> list[str] | None:
        """Return the argv list for ``project``, or emit an error and ``None``."""
        if project.type == "lein":
            raw = settings.get("repl", "lein_command", "lein repl :headless")
        elif project.type == "deps":
            raw = settings.get("repl", "clj_command", "clj -M:nrepl")
        else:
            self.error_signal.emit(
                "Cannot start REPL for non-Clojure project "
                f"({project.type}): {project.root}",
            )
            return None
        try:
            parts = shlex.split(str(raw))
        except ValueError as exc:
            self.error_signal.emit(f"Invalid REPL command ({raw!r}): {exc}")
            return None
        if not parts:
            self.error_signal.emit(
                f"Empty REPL command for project type '{project.type}'",
            )
            return None
        return parts

    # --------------------------------------------------------- stream pump

    def _on_ready_stdout(self) -> None:
        """Drain stdout bytes from the QProcess into the output pump."""
        proc = self._proc
        if proc is None:
            return
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._pump("stdout", data)

    def _on_ready_stderr(self) -> None:
        """Drain stderr bytes from the QProcess into the output pump."""
        proc = self._proc
        if proc is None:
            return
        data = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        self._pump("stderr", data)

    def _pump(self, stream: str, data: str) -> None:
        """Split ``data`` into lines, emit each, and feed the port detector."""
        if not data:
            return
        if stream == "stdout":
            self._stdout_buf += data
            buf = self._stdout_buf
        else:
            self._stderr_buf += data
            buf = self._stderr_buf
        lines: list[str] = []
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            lines.append(line.rstrip("\r"))
        if stream == "stdout":
            self._stdout_buf = buf
        else:
            self._stderr_buf = buf

        for line in lines:
            self.output_line_signal.emit(line, stream)
            if self._port is None:
                port = self._detector.feed(line + "\n")
                if port is not None:
                    self._port = port
                    if self._state == "starting":
                        self._emit_state("running")
                    self.port_detected_signal.emit(port)

    # -------------------------------------------------- termination handling

    def _on_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Handle child termination: clean stop vs. crash classification."""
        self._flush_trailing_buffers()
        proc = self._proc
        self._proc = None
        if proc is not None:
            proc.deleteLater()

        if self._expecting_stop:
            log.info("nREPL process exited cleanly (code=%d).", exit_code)
            self._emit_state("stopped")
            self._expecting_stop = False
            return

        status_name = (
            "crashed"
            if exit_status == QProcess.ExitStatus.CrashExit
            else f"exit {exit_code}"
        )
        message = f"nREPL process terminated unexpectedly ({status_name})."
        log.warning(message)
        self.error_signal.emit(message)
        self._emit_state("crashed")

    def _on_errored(self, error: QProcess.ProcessError) -> None:
        """Translate low-level QProcess errors into user-visible messages."""
        if error == QProcess.ProcessError.FailedToStart:
            msg = "Failed to start REPL command (is lein/clj on PATH?)."
            self.error_signal.emit(msg)
            proc = self._proc
            self._proc = None
            if proc is not None:
                proc.deleteLater()
            self._emit_state("idle")
            return
        log.debug("QProcess error: %s", error)

    def _flush_trailing_buffers(self) -> None:
        """Emit any pending partial lines still in the stream buffers."""
        if self._stdout_buf:
            self.output_line_signal.emit(self._stdout_buf, "stdout")
            self._stdout_buf = ""
        if self._stderr_buf:
            self.output_line_signal.emit(self._stderr_buf, "stderr")
            self._stderr_buf = ""

    # ------------------------------------------------------------ internals

    def _emit_state(self, state: ProcessState) -> None:
        """Broadcast a state transition unless it is a no-op."""
        if state == self._state:
            return
        self._state = state
        self.process_state_signal.emit(state)
