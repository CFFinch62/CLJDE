"""Regex helpers for detecting an nREPL server's listening port.

Pure module; no Qt imports. :func:`detect_port_in_line` inspects a
single output line and returns the port if it matches any of the
known nREPL startup banners. :class:`PortDetector` is a tiny
line-buffered adapter for chunked process output: callers push
whatever ``readyRead`` gave them and get the port back once a full
banner line has arrived.
"""

from __future__ import annotations

import re

# Matches the three banner variants shipped by Leiningen, tools.deps,
# and nREPL itself. Anchored only to the literal prefix so trailing
# text (host, uri, etc.) is ignored.
_PORT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"nREPL server started on port\s+(\d+)"),
    re.compile(r"Started nREPL server at\s+[^:\s]*:(\d+)"),
    re.compile(r"nrepl://[^:\s]+:(\d+)"),
)

_MIN_PORT = 1
_MAX_PORT = 65535


def detect_port_in_line(line: str) -> int | None:
    """Return the nREPL port parsed from ``line``, or ``None`` if absent."""
    if not line:
        return None
    for pattern in _PORT_PATTERNS:
        match = pattern.search(line)
        if match is None:
            continue
        try:
            port = int(match.group(1))
        except ValueError:
            continue
        if _MIN_PORT <= port <= _MAX_PORT:
            return port
    return None


class PortDetector:
    """Line-buffered port scanner for streaming nREPL process output."""

    def __init__(self) -> None:
        self._buffer: str = ""
        self._port: int | None = None

    def feed(self, chunk: str) -> int | None:
        """Append ``chunk`` and return the port as soon as a banner completes.

        Once a port has been detected, subsequent calls are no-ops that
        return the cached value. Lines without a trailing newline are
        held back so the detector never fires on a truncated number.
        """
        if self._port is not None:
            return self._port
        if not chunk:
            return None
        self._buffer += chunk
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            port = detect_port_in_line(line.rstrip("\r"))
            if port is not None:
                self._port = port
                return port
        return None

    def reset(self) -> None:
        """Clear state so the same detector instance can watch a new process."""
        self._buffer = ""
        self._port = None

    def port(self) -> int | None:
        """Return the detected port, if any."""
        return self._port
