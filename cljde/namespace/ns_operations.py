"""Fire-and-forget namespace operations for the nREPL client.

Each public function builds an eval message, ships it through the
supplied :class:`NreplClient`, and returns the request id (or
``None`` if the client has no active session). Responses are routed
through :attr:`NreplClient.response_signal`; the REPL pane already
renders ``value``/``out``/``err`` payloads, so these helpers do not
need to hook their own listeners.

:func:`list_all_ns` is the exception: the namespace browser
subscribes to ``response_signal`` directly, matches the returned id,
and populates itself from the aggregated ``value`` payload.
"""

from __future__ import annotations

import logging

from cljde.nrepl import messages
from cljde.nrepl.client import NreplClient

log = logging.getLogger(__name__)

_REFRESH_CODE = (
    "(try (require 'clojure.tools.namespace.repl)"
    " ((resolve 'clojure.tools.namespace.repl/refresh))"
    " (catch Throwable _ :cljde/refresh-unavailable))"
)

_LIST_CODE = "(sort (map str (map ns-name (all-ns))))"


def reload_ns(client: NreplClient, ns_name: str) -> str | None:
    """Send ``(require 'NS :reload)`` on the default session."""
    return _send(client, f"(require '{ns_name} :reload)")


def reload_all_changed(client: NreplClient) -> str | None:
    """Invoke ``clojure.tools.namespace.repl/refresh`` if available."""
    return _send(client, _REFRESH_CODE)


def switch_ns(client: NreplClient, ns_name: str) -> str | None:
    """Send ``(in-ns 'NS)`` on the default session."""
    return _send(client, f"(in-ns '{ns_name})")


def remove_ns(client: NreplClient, ns_name: str) -> str | None:
    """Send ``(remove-ns 'NS)`` on the default session."""
    return _send(client, f"(remove-ns '{ns_name})")


def list_all_ns(client: NreplClient) -> str | None:
    """Send the all-namespace query; return the request id for correlation."""
    return _send(client, _LIST_CODE)


def _send(client: NreplClient, code: str) -> str | None:
    """Build and send an eval request; return its id or ``None``."""
    if not client.is_connected():
        log.debug("ns op skipped; client not connected: %s", code)
        return None
    session = client.default_session()
    if session is None:
        log.debug("ns op skipped; no default session: %s", code)
        return None
    msg = messages.build_eval(code=code, session=session)
    client.send(msg)
    return msg["id"]
