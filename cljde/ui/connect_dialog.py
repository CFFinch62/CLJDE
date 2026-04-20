"""Modal dialog prompting for an nREPL host and port.

On accept, the chosen endpoint is written back to the ``repl`` section
of :class:`cljde.config.settings.Settings` so it persists across runs.
Use :meth:`ConnectDialog.prompt` as the canonical entry point; it
returns the chosen ``(host, port)`` pair or ``None`` on cancel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from cljde.config.settings import Settings

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7888
MIN_PORT = 1
MAX_PORT = 65535


class ConnectDialog(QDialog):
    """Ask the user for an external nREPL host/port."""

    def __init__(self, settings: "Settings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("Connect to nREPL")
        self.setModal(True)
        self.setObjectName("connectDialog")

        self._host_edit = QLineEdit(self)
        self._host_edit.setObjectName("connectHostEdit")
        self._host_edit.setText(
            str(settings.get("repl", "default_host", DEFAULT_HOST)) or DEFAULT_HOST,
        )

        self._port_spin = QSpinBox(self)
        self._port_spin.setObjectName("connectPortSpin")
        self._port_spin.setRange(MIN_PORT, MAX_PORT)
        saved_port = _coerce_port(settings.get("repl", "default_port", 0))
        self._port_spin.setValue(saved_port)

        form = QFormLayout()
        form.addRow("Host:", self._host_edit)
        form.addRow("Port:", self._port_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Connect")
            ok_button.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._host_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------ public API

    def host(self) -> str:
        """Return the trimmed host value entered by the user."""
        return self._host_edit.text().strip() or DEFAULT_HOST

    def port(self) -> int:
        """Return the port value entered by the user."""
        return int(self._port_spin.value())

    @staticmethod
    def prompt(
        settings: "Settings", parent: QWidget | None = None,
    ) -> tuple[str, int] | None:
        """Show the dialog modally and return ``(host, port)`` or ``None``."""
        dialog = ConnectDialog(settings, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        host = dialog.host()
        port = dialog.port()
        settings.set("repl", "default_host", host)
        settings.set("repl", "default_port", port)
        try:
            settings.save()
        except Exception:  # pragma: no cover - defensive persistence
            pass
        return host, port


def _coerce_port(raw: object) -> int:
    """Return a valid port integer, falling back to :data:`DEFAULT_PORT`."""
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_PORT
    if MIN_PORT <= value <= MAX_PORT:
        return value
    return DEFAULT_PORT
