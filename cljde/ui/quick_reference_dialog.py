"""Quick Reference dialog: Clojure cheat sheet plus CLJDE keybindings.

A modal :class:`QDialog` with two tabs rendered as rich-text HTML in a
:class:`QTextBrowser`. The content is deliberately static — no
external doc-generation step — so the dialog can be opened instantly
from the Help menu without hitting disk or the REPL.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from cljde.config.theme import DEFAULT_PALETTE
from cljde.ui.quick_reference_content import CLJDE_SHORTCUTS_HTML, CLOJURE_CHEATSHEET_HTML

DIALOG_MIN_WIDTH = 720
DIALOG_MIN_HEIGHT = 560


class QuickReferenceDialog(QDialog):
    """Help > Quick Reference dialog: Clojure cheat sheet + CLJDE shortcuts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CLJDE Quick Reference")
        self.setObjectName("quickReferenceDialog")
        self.setModal(True)
        self.setMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("quickReferenceTabs")
        self._tabs.addTab(_build_browser(CLOJURE_CHEATSHEET_HTML), "Clojure")
        self._tabs.addTab(_build_browser(CLJDE_SHORTCUTS_HTML), "CLJDE Shortcuts")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setDefault(True)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs, 1)
        layout.addWidget(buttons, 0)

        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self.reject)

    @staticmethod
    def show_for(parent: QWidget | None = None) -> None:
        """Construct and show the dialog modally; destroy on close."""
        dialog = QuickReferenceDialog(parent)
        dialog.exec()


def _build_browser(html: str) -> QTextBrowser:
    """Return a themed :class:`QTextBrowser` rendering ``html``."""
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setOpenLinks(False)
    browser.setHtml(_wrap_with_style(html))
    return browser


def _wrap_with_style(body_html: str) -> str:
    """Return ``body_html`` embedded in a minimal themed HTML document."""
    p = DEFAULT_PALETTE
    return (
        "<html><head><style>"
        f"body {{ color: {p.foreground}; background-color: {p.background_dark}; "
        "font-family: monospace; font-size: 11pt; }}"
        f"h2 {{ color: {p.amber_primary}; margin-top: 14px; "
        "margin-bottom: 4px; }}"
        f"code, kbd {{ color: {p.blue_primary}; }}"
        f"table {{ border-collapse: collapse; margin: 4px 0 12px 0; }}"
        f"td {{ padding: 2px 10px 2px 0; vertical-align: top; }}"
        f"td.name {{ color: {p.amber_primary}; white-space: nowrap; }}"
        f"td.desc {{ color: {p.foreground}; }}"
        f"p.lead {{ color: {p.foreground_dim}; margin: 2px 0 8px 0; }}"
        "</style></head><body>" + body_html + "</body></html>"
    )
