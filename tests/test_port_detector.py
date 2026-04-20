"""Tests for :mod:`cljde.repl.port_detector`."""

from __future__ import annotations

from cljde.repl.port_detector import PortDetector, detect_port_in_line


# --------------------------------------------------------- line-level regex

def test_detects_lein_banner_with_host() -> None:
    """Full Leiningen banner with ``on host`` suffix parses."""
    line = "nREPL server started on port 56789 on host 127.0.0.1"
    assert detect_port_in_line(line) == 56789


def test_detects_plain_on_port_banner() -> None:
    """Banner without the ``on host`` suffix still parses."""
    assert detect_port_in_line("nREPL server started on port 12345") == 12345


def test_detects_started_at_form() -> None:
    """The ``Started nREPL server at :PORT`` variant parses."""
    assert detect_port_in_line("Started nREPL server at :7888") == 7888


def test_detects_nrepl_uri_variant() -> None:
    """A ``nrepl://host:port`` URI line is also accepted."""
    assert detect_port_in_line("nrepl://127.0.0.1:4321 ready") == 4321


def test_unrelated_output_returns_none() -> None:
    """Lines without a recognised port yield ``None``."""
    assert detect_port_in_line("Compiling my.ns") is None
    assert detect_port_in_line("") is None
    assert detect_port_in_line("some random text 12345") is None


def test_rejects_out_of_range_port_number() -> None:
    """A port value outside 1..65535 is not considered valid."""
    assert detect_port_in_line("nREPL server started on port 0") is None
    assert detect_port_in_line("nREPL server started on port 70000") is None


# --------------------------------------------------------- buffered detector

def test_detector_emits_once_on_complete_line() -> None:
    """A single complete line through ``feed`` yields the port exactly once."""
    det = PortDetector()
    assert det.feed("nREPL server started on port 5555\n") == 5555
    assert det.port() == 5555


def test_detector_ignores_unrelated_lines() -> None:
    """Noise before the banner does not trigger detection."""
    det = PortDetector()
    assert det.feed("loading deps...\n") is None
    assert det.feed("compiling...\n") is None
    assert det.port() is None


def test_detector_handles_lines_split_across_chunks() -> None:
    """A banner split mid-line across chunks is detected when it completes."""
    det = PortDetector()
    assert det.feed("nREPL server ") is None
    assert det.feed("started on port 99") is None
    assert det.feed("88 on host 127.0.0.1\n") == 9988
    assert det.port() == 9988


def test_detector_handles_many_chunks_without_newline() -> None:
    """No newline means no detection, however much data accumulates."""
    det = PortDetector()
    for piece in ("nREPL ", "server ", "started ", "on port ", "1234"):
        assert det.feed(piece) is None
    assert det.feed("\n") == 1234


def test_detector_ignores_lines_after_port_found() -> None:
    """Once a port is cached, subsequent lines do not overwrite it."""
    det = PortDetector()
    det.feed("nREPL server started on port 5555\n")
    assert det.feed("Started nREPL server at :1234\n") == 5555
    assert det.feed("nrepl://127.0.0.1:4321\n") == 5555
    assert det.port() == 5555


def test_detector_reset_clears_state() -> None:
    """After ``reset`` the detector behaves like a fresh instance."""
    det = PortDetector()
    det.feed("nREPL server started on port 7777\n")
    assert det.port() == 7777
    det.reset()
    assert det.port() is None
    assert det.feed("still warming up...\n") is None
    assert det.feed("nREPL server started on port 8888\n") == 8888


def test_detector_accepts_crlf_line_endings() -> None:
    """Windows-style ``\\r\\n`` line endings do not confuse the regex."""
    det = PortDetector()
    assert det.feed("nREPL server started on port 4242\r\n") == 4242


def test_detector_handles_multiple_lines_per_chunk() -> None:
    """A single chunk containing several lines is split correctly."""
    det = PortDetector()
    chunk = (
        "warming up\n"
        "loading clojure.core\n"
        "nREPL server started on port 3333 on host 127.0.0.1\n"
        "ready\n"
    )
    assert det.feed(chunk) == 3333
