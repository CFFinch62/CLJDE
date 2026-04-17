"""CLIDE launcher script.

Run with ``python main.py`` from the repository root. Initialises
logging (rotating file + console) before instantiating Qt so that any
startup errors are captured in ``clide.log`` inside the per-user config
directory.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from clide import __version__
from clide.app import run
from clide.config.paths import ensure_config_dir, log_path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


def configure_logging() -> None:
    """Install a rotating file handler (DEBUG) and console handler (INFO)."""
    ensure_config_dir()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    file_handler = RotatingFileHandler(
        log_path(),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def main() -> int:
    """Script entry point: configure logging, launch CLIDE, return rc."""
    configure_logging()
    log = logging.getLogger("clide.main")
    log.info("--- CLIDE %s launching ---", __version__)
    log.info("Log file: %s", log_path())
    try:
        return run(sys.argv)
    except Exception:
        log.exception("Fatal error during CLIDE startup.")
        return 1
    finally:
        log.info("--- CLIDE shutdown ---")


if __name__ == "__main__":
    raise SystemExit(main())
