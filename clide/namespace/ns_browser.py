"""Docked namespace browser driven by nREPL responses.

Queries the connected REPL for ``(all-ns)`` and keeps a
filter-capable list view in sync. The active namespace is highlighted
in amber; right-click exposes Switch / Reload / Remove. The widget
itself does not send mutations — it emits signals that the main
window forwards through :mod:`clide.namespace.ns_operations`.
"""

from __future__ import annotations

import logging
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clide.config.theme import DEFAULT_PALETTE
from clide.namespace import ns_operations
from clide.nrepl.client import NreplClient

log = logging.getLogger(__name__)

_STRING_RE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')


class NsBrowser(QWidget):
    """List of REPL-loaded namespaces with filter, refresh, and context menu."""

    switch_ns_signal = pyqtSignal(str)
    reload_ns_signal = pyqtSignal(str)
    remove_ns_signal = pyqtSignal(str)

    def __init__(self, client: NreplClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._all_ns: list[str] = []
        self._current_ns = "user"
        self._pending_id: str | None = None
        self._accumulator: list[str] = []

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------ public API

    def refresh(self) -> None:
        """Request the current ``(all-ns)`` list from the REPL."""
        msg_id = ns_operations.list_all_ns(self._client)
        if msg_id is None:
            return
        self._pending_id = msg_id
        self._accumulator.clear()

    def set_current_ns(self, ns: str) -> None:
        """Mark ``ns`` as the active REPL namespace and repaint the list."""
        if ns == self._current_ns:
            return
        self._current_ns = ns
        self._rebuild_list()

    def all_namespaces(self) -> list[str]:
        """Return a snapshot of the last-known namespace list."""
        return list(self._all_ns)

    def current_ns(self) -> str:
        """Return the namespace currently marked as active."""
        return self._current_ns

    # ---------------------------------------------------------- UI plumbing

    def _build_ui(self) -> None:
        """Assemble the filter / refresh strip and the list view."""
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(4)
        title = QLabel("Namespaces")
        title.setObjectName("nsBrowserTitle")
        title.setStyleSheet(
            f"color: {DEFAULT_PALETTE.amber_primary}; font-weight: bold;"
        )
        header.addWidget(title, 1)
        self._refresh_btn = QPushButton("Refresh", self)
        self._refresh_btn.setObjectName("nsBrowserRefresh")
        self._refresh_btn.setFlat(True)
        header.addWidget(self._refresh_btn, 0)
        root.addLayout(header)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("nsBrowserFilter")
        self._filter.setPlaceholderText("Filter...")
        root.addWidget(self._filter)

        self._list = QListWidget(self)
        self._list.setObjectName("nsBrowserList")
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        root.addWidget(self._list, 1)

    def _wire_signals(self) -> None:
        """Hook client responses and user interactions into local slots."""
        self._client.response_signal.connect(self._on_response)
        self._client.connection_state_signal.connect(self._on_state)
        self._refresh_btn.clicked.connect(self.refresh)
        self._filter.textChanged.connect(lambda _t: self._rebuild_list())
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    # ----------------------------------------------------- signal handlers

    def _on_response(self, msg_id: str, response: dict) -> None:
        """Accumulate list responses whose id matches the pending request."""
        if msg_id != self._pending_id:
            return
        value = response.get("value")
        if isinstance(value, str):
            self._accumulator.append(value)
        status = response.get("status")
        if isinstance(status, list) and "done" in status:
            joined = "".join(self._accumulator)
            self._all_ns = _parse_ns_list(joined)
            self._pending_id = None
            self._accumulator.clear()
            self._rebuild_list()

    def _on_state(self, state: str) -> None:
        """Clear or repopulate the list on connection transitions."""
        if state == "disconnected":
            self._all_ns = []
            self._pending_id = None
            self._accumulator.clear()
            self._rebuild_list()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Request a switch to the double-clicked namespace."""
        name = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(name, str) and name:
            self.switch_ns_signal.emit(name)

    def _on_context_menu(self, position: object) -> None:
        """Show the per-namespace Switch/Reload/Remove menu."""
        item = self._list.itemAt(position) if hasattr(position, "x") else None
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str) or not name:
            return
        menu = QMenu(self)
        switch = QAction(f"Switch to {name}", menu)
        reload_a = QAction("Reload", menu)
        remove = QAction("Remove", menu)
        switch.triggered.connect(lambda: self.switch_ns_signal.emit(name))
        reload_a.triggered.connect(lambda: self.reload_ns_signal.emit(name))
        remove.triggered.connect(lambda: self.remove_ns_signal.emit(name))
        menu.addAction(switch)
        menu.addAction(reload_a)
        menu.addSeparator()
        menu.addAction(remove)
        menu.exec(self._list.viewport().mapToGlobal(position))

    # --------------------------------------------------------- rendering

    def _rebuild_list(self) -> None:
        """Refresh the visible list, respecting the current filter."""
        needle = self._filter.text().strip().lower()
        self._list.clear()
        amber = QBrush(QColor(DEFAULT_PALETTE.amber_primary))
        for name in self._all_ns:
            if needle and needle not in name.lower():
                continue
            label = f"• {name}" if name == self._current_ns else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            if name == self._current_ns:
                item.setForeground(amber)
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            self._list.addItem(item)


def _parse_ns_list(value: str) -> list[str]:
    """Extract namespace names from the stringified ``(map str (all-ns))`` value."""
    names = _STRING_RE.findall(value)
    return sorted(dict.fromkeys(names))
