"""Modal fuzzy-match namespace picker.

Invoked by ``Ctrl+Shift+N``. Shows a text box and a list of
candidates pre-filled from the namespace browser's cached list. Each
keystroke re-scores candidates using a subsequence match (a streak
bonus so runs of consecutive matches outrank scattered hits) and the
top results are shown in a :class:`QListWidget`. Enter confirms the
highlighted choice; :meth:`prompt` returns the chosen namespace name
or ``None`` on cancel.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class FuzzyNsDialog(QDialog):
    """Modal dialog for fuzzy-selecting a namespace."""

    def __init__(
        self,
        namespaces: list[str],
        current_ns: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._namespaces = list(namespaces)
        self._current_ns = current_ns

        self.setWindowTitle("Go to Namespace")
        self.setModal(True)
        self.setObjectName("fuzzyNsDialog")
        self.resize(420, 360)

        self._query = QLineEdit(self)
        self._query.setObjectName("fuzzyNsQuery")
        self._query.setPlaceholderText("Type to filter namespaces...")

        self._list = QListWidget(self)
        self._list.setObjectName("fuzzyNsList")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self._query)
        layout.addWidget(self._list, 1)

        self._query.textChanged.connect(self._rebuild)
        self._list.itemActivated.connect(lambda _i: self.accept())
        self._query.installEventFilter(self)

        self._rebuild("")
        self._query.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------ public API

    def selected(self) -> str | None:
        """Return the currently highlighted namespace, or ``None``."""
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def prompt(
        namespaces: list[str],
        current_ns: str | None = None,
        parent: QWidget | None = None,
    ) -> str | None:
        """Show the dialog modally; return the chosen ns or ``None``."""
        dialog = FuzzyNsDialog(namespaces, current_ns, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected()

    # -------------------------------------------------------- key handling

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        """Redirect Up/Down/Enter on the line edit to the list widget."""
        if obj is self._query and isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self._list.keyPressEvent(event)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._list.currentItem() is not None:
                    self.accept()
                return True
        return super().eventFilter(obj, event)

    # ----------------------------------------------------------- scoring

    def _rebuild(self, text: str) -> None:
        """Re-score and repopulate the candidate list for ``text``."""
        query = (text or "").strip()
        scored: list[tuple[int, str]] = []
        for name in self._namespaces:
            score = fuzzy_score(query, name)
            if score is None:
                continue
            scored.append((-score, name))
        scored.sort(key=lambda pair: (pair[0], pair[1]))

        self._list.clear()
        for _neg, name in scored:
            label = f"• {name}" if name == self._current_ns else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)


def fuzzy_score(query: str, candidate: str) -> int | None:
    """Return a subsequence-match score for ``query`` in ``candidate``.

    ``None`` means the characters of ``query`` cannot be found in order
    inside ``candidate``. Higher scores rank better: each run of
    consecutive matches contributes quadratically, so ``"str"`` beats
    ``"s.t.r"`` on ``"clojure.string"``.
    """
    if not query:
        return 0
    q = query.lower()
    c = candidate.lower()
    qi = 0
    streak = 0
    score = 0
    for ch in c:
        if qi < len(q) and ch == q[qi]:
            qi += 1
            streak += 1
            score += streak * streak
        else:
            streak = 0
    if qi < len(q):
        return None
    return score
