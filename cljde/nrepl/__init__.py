"""nREPL protocol client for CLJDE.

This package implements the wire-level plumbing for talking to an
external nREPL server: bencode codec, message builders, a Qt-threaded
socket worker, and a high-level :class:`NreplClient` that exposes
responses as Qt signals. No UI code lives here; Phase 5 consumes this
package from the REPL widgets.
"""

from __future__ import annotations

from cljde.nrepl.bencode import BencodeError, decode, decode_all, encode
from cljde.nrepl.client import NreplClient
from cljde.nrepl.session import Session, SessionManager
from cljde.nrepl.socket_worker import SocketWorker

__all__ = [
    "BencodeError",
    "NreplClient",
    "Session",
    "SessionManager",
    "SocketWorker",
    "decode",
    "decode_all",
    "encode",
]
