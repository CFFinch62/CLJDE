"""Main menu bar construction for CLJDE.

Builds the File / Edit / View / REPL / Help menus and wires every item
to a stub method on the main window. The stubs log a
``not implemented: <menu path>`` message so clicking through the UI
produces a visible trail in the log file for Phase 1 verification.

Menu construction is table-driven: each entry is a tuple of
``(label, shortcut, slot_name, checkable)``. A ``None`` label inserts
a separator. This keeps the file compact and makes it trivial to
extend in later phases without hand-rolling ``QAction`` wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMenu, QMenuBar, QWidget

if TYPE_CHECKING:
    from cljde.main_window import MainWindow


MenuEntry = tuple[str | None, str | None, str | None, bool]

FILE_MENU: list[MenuEntry] = [
    ("New",           "Ctrl+N",        "stub_file_new",          False),
    ("Open File...",  "Ctrl+O",        "stub_file_open",         False),
    ("Open Project...", "Ctrl+Shift+O","stub_file_open_project", False),
    (None, None, None, False),
    ("Save",          "Ctrl+S",        "stub_file_save",         False),
    ("Save As...",    "Ctrl+Shift+S",  "stub_file_save_as",      False),
    (None, None, None, False),
    ("Recent Files",  None,            "stub_file_recent",       False),
    ("Go to Namespace...", "Ctrl+Shift+N", "stub_file_goto_namespace", False),
    (None, None, None, False),
    ("Exit",          "Ctrl+Q",        "stub_file_exit",         False),
]

EDIT_MENU: list[MenuEntry] = [
    ("Undo",  "Ctrl+Z",       "stub_edit_undo",  False),
    ("Redo",  "Ctrl+Shift+Z", "stub_edit_redo",  False),
    (None, None, None, False),
    ("Cut",   "Ctrl+X",       "stub_edit_cut",   False),
    ("Copy",  "Ctrl+C",       "stub_edit_copy",  False),
    ("Paste", "Ctrl+V",       "stub_edit_paste", False),
    (None, None, None, False),
    ("Find...", "Ctrl+F",     "stub_edit_find",  False),
]

VIEW_MENU: list[MenuEntry] = [
    ("Toggle File Tree",   "F9",      "stub_view_toggle_tree",        True),
    ("Toggle REPL",        "F10",     "stub_view_toggle_repl",        True),
    ("Toggle Namespaces",  "F11",     "stub_view_toggle_namespaces",  True),
    (None, None, None, False),
    ("Show Hidden Files",  None,      "stub_view_show_hidden",        True),
    ("Rainbow Parens",     None,      "stub_view_rainbow_parens",     True),
    (None, None, None, False),
    ("Full Screen",        "F12",     "stub_view_full_screen",        True),
]

REPL_MENU: list[MenuEntry] = [
    ("Start",            None,               "stub_repl_start",      False),
    ("Stop",             None,               "stub_repl_stop",       False),
    ("Restart",          None,               "stub_repl_restart",    False),
    ("Connect External...", None,            "stub_repl_connect",    False),
    ("Disconnect",       None,               "stub_repl_disconnect", False),
    (None, None, None, False),
    ("Eval Form",        "Ctrl+Return",      "stub_eval_form",       False),
    ("Eval Selection",   "Ctrl+Shift+Return","stub_eval_selection",  False),
    ("Eval File",        "Ctrl+Alt+Return",  "stub_eval_file",       False),
    (None, None, None, False),
    ("Reload Current NS",     "Ctrl+R",         "stub_repl_reload_current_ns",  False),
    ("Switch to File NS",     "Ctrl+Shift+R",   "stub_repl_switch_to_file_ns",  False),
    ("Reload All Changed NS", "Ctrl+Shift+F5",  "stub_repl_reload_all_changed", False),
]

HELP_MENU: list[MenuEntry] = [
    ("About CLJDE",    None, "stub_help_about",    False),
    ("Shortcuts",      "F1", "stub_help_shortcuts", False),
    (None, None, None, False),
    ("Report Issue...", None, "stub_help_report_issue", False),
]

MENU_LAYOUT: list[tuple[str, list[MenuEntry]]] = [
    ("&File",  FILE_MENU),
    ("&Edit",  EDIT_MENU),
    ("&View",  VIEW_MENU),
    ("&REPL",  REPL_MENU),
    ("&Help",  HELP_MENU),
]


def build_menu_bar(window: "MainWindow") -> QMenuBar:
    """Construct and return the CLJDE menu bar wired to ``window``'s stubs."""
    bar = QMenuBar(window)
    bar.setNativeMenuBar(False)  # keep menus inside the window on macOS too
    for title, entries in MENU_LAYOUT:
        menu = bar.addMenu(title)
        _populate_menu(menu, entries, window)
    return bar


def _populate_menu(
    menu: QMenu,
    entries: list[MenuEntry],
    window: "MainWindow",
) -> None:
    """Add actions and separators from ``entries`` to ``menu``."""
    for label, shortcut, slot_name, checkable in entries:
        if label is None:
            menu.addSeparator()
            continue
        slot = _resolve_slot(window, slot_name, f"{menu.title()} | {label}")
        action = _make_action(menu, label, shortcut, slot, checkable, slot_name)
        menu.addAction(action)


def _make_action(
    parent: QWidget,
    label: str,
    shortcut: str | None,
    slot: Callable[[], None],
    checkable: bool,
    object_name: str | None = None,
) -> QAction:
    """Create a configured ``QAction`` connected to ``slot``."""
    action = QAction(label, parent)
    if object_name:
        action.setObjectName(object_name)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    action.setAutoRepeat(False)
    action.setCheckable(checkable)
    if checkable:
        action.toggled.connect(lambda checked, s=slot: s(checked))
    else:
        action.triggered.connect(slot)
    return action


def _resolve_slot(
    window: "MainWindow",
    slot_name: str | None,
    menu_path: str,
) -> Callable[..., None]:
    """Return the named stub method on ``window``, or a fallback logger."""
    if slot_name and hasattr(window, slot_name):
        return getattr(window, slot_name)
    return lambda *_args, _p=menu_path: window.log_not_implemented(_p)
