"""Help menu dialogs.

:func:`show_about` renders the About CLJDE message via
:class:`QMessageBox`, reporting the package version and the running
Python and Qt runtimes.
"""

from __future__ import annotations

import platform
import sys

from PyQt6.QtCore import QT_VERSION_STR
from PyQt6.QtWidgets import QMessageBox, QWidget

from cljde import __version__


def show_about(parent: QWidget | None = None) -> None:
    """Display the About CLJDE dialog."""
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    body = (
        f"<h3>CLJDE {__version__}</h3>"
        "<p>A Clojure-focused integrated development environment "
        "built on Python and PyQt6.</p>"
        f"<p><b>Python:</b> {py}<br>"
        f"<b>Qt:</b> {QT_VERSION_STR}<br>"
        f"<b>Platform:</b> {platform.system()} {platform.release()}</p>"
        "<p>&copy; Fragillidae Software &mdash; MIT License.</p>"
    )
    QMessageBox.about(parent, "About CLJDE", body)
