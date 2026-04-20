"""QApplication factory and top-level ``main`` entry point for CLJDE.

Prefers a factory function over a ``QApplication`` subclass so the
application can be constructed and torn down cleanly from tests and
from the ``console_scripts`` entry point declared in ``pyproject.toml``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import QApplication

from cljde import __version__
from cljde.config.settings import Settings
from cljde.config.theme import DEFAULT_PALETTE, build_stylesheet

log = logging.getLogger(__name__)

ORG_NAME = "Fragillidae Software"
ORG_DOMAIN = "fragillidae.invalid"
APP_NAME = "CLJDE"
ICON_FILENAME = "cljde-icon.svg"


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Build a fully-configured ``QApplication`` for CLJDE."""
    argv_list = list(argv) if argv is not None else list(sys.argv)

    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setOrganizationDomain(ORG_DOMAIN)
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    QGuiApplication.setDesktopFileName("cljde")

    app = QApplication.instance()
    if app is None:
        app = QApplication(argv_list)
    assert isinstance(app, QApplication)  # developer invariant

    apply_window_icon(app)
    apply_theme(app)
    log.debug("QApplication configured (org=%r, app=%r).", ORG_NAME, APP_NAME)
    return app


def apply_window_icon(app: QApplication) -> None:
    """Install the shared CLJDE window icon if the SVG asset is available."""
    icon_path = Path(__file__).resolve().parent.parent / "images" / ICON_FILENAME
    if not icon_path.is_file():
        log.debug("Window icon %s not found; skipping.", icon_path)
        return
    app.setWindowIcon(QIcon(str(icon_path)))
    log.debug("Window icon loaded from %s", icon_path)


def apply_theme(app: QApplication) -> None:
    """Apply the CLJDE QSS stylesheet to ``app``."""
    qss = build_stylesheet(DEFAULT_PALETTE)
    app.setStyleSheet(qss)
    log.debug("Applied CLJDE stylesheet (%d chars).", len(qss))


def run(argv: Sequence[str] | None = None) -> int:
    """Launch CLJDE and return the process exit code."""
    # Local import avoids loading Qt widgets during ``cljde`` module import
    # in non-GUI contexts (e.g. tests).
    from cljde.main_window import MainWindow

    app = create_application(argv)
    settings = Settings.load()
    window = MainWindow(settings)
    window.show()
    log.info("CLJDE %s started.", __version__)
    return app.exec()


def main() -> int:
    """Console-script entry point."""
    return run(sys.argv)
