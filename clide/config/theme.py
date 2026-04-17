"""CLIDE colour palette and QSS stylesheet generator.

Defines the amber/blue/dark palette used across the application and
produces a Qt stylesheet string that skins the default widget set.
The palette is exposed as a dataclass so other modules (syntax
highlighter, REPL pane) can reference the same colour names.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Palette:
    """Named colours for the CLIDE theme (hex strings)."""

    background_dark: str = "#1a1a1a"
    background_medium: str = "#252525"
    background_light: str = "#2d2d2d"
    foreground: str = "#e0e0e0"
    foreground_dim: str = "#a0a0a0"
    amber_primary: str = "#ffb000"
    amber_bright: str = "#ffcc44"
    blue_primary: str = "#4a90e2"
    blue_bright: str = "#6bb6ff"
    error_red: str = "#e04848"
    success_green: str = "#50c878"

    def as_dict(self) -> dict[str, str]:
        """Return the palette as an ordinary dictionary."""
        return asdict(self)


DEFAULT_PALETTE = Palette()


def build_stylesheet(palette: Palette = DEFAULT_PALETTE) -> str:
    """Return a Qt stylesheet string skinning the default widget set."""
    p = palette
    return f"""
    QWidget {{
        background-color: {p.background_dark};
        color: {p.foreground};
        font-family: "DejaVu Sans", "Segoe UI", sans-serif;
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{
        background-color: {p.background_dark};
    }}
    QMenuBar {{
        background-color: {p.background_medium};
        color: {p.foreground};
        border-bottom: 1px solid {p.background_light};
    }}
    QMenuBar::item:selected {{
        background-color: {p.amber_primary};
        color: {p.background_dark};
    }}
    QMenu {{
        background-color: {p.background_medium};
        color: {p.foreground};
        border: 1px solid {p.background_light};
    }}
    QMenu::item:selected {{
        background-color: {p.amber_primary};
        color: {p.background_dark};
    }}
    QToolBar {{
        background-color: {p.background_medium};
        border: none;
        spacing: 4px;
        padding: 2px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {p.foreground};
        border: 1px solid transparent;
        padding: 4px 8px;
        border-radius: 3px;
    }}
    QToolButton:hover {{
        background-color: {p.background_light};
        border-color: {p.amber_primary};
        color: {p.amber_bright};
    }}
    QToolButton:pressed {{
        background-color: {p.amber_primary};
        color: {p.background_dark};
    }}
    QStatusBar {{
        background-color: {p.background_medium};
        color: {p.foreground_dim};
        border-top: 1px solid {p.background_light};
    }}
    QStatusBar QLabel {{
        color: {p.foreground_dim};
        padding: 0 8px;
    }}
    QDockWidget {{
        color: {p.foreground};
        titlebar-close-icon: none;
    }}
    QDockWidget::title {{
        background-color: {p.background_medium};
        color: {p.amber_primary};
        padding: 4px 8px;
        border-bottom: 1px solid {p.background_light};
    }}
    QLabel {{
        color: {p.foreground};
        background-color: transparent;
    }}
    QPlainTextEdit, QTextEdit, QLineEdit {{
        background-color: {p.background_medium};
        color: {p.foreground};
        border: 1px solid {p.background_light};
        selection-background-color: {p.blue_primary};
        selection-color: {p.background_dark};
    }}
    QTabWidget::pane {{
        background-color: {p.background_medium};
        border: 1px solid {p.background_light};
    }}
    QTabBar::tab {{
        background-color: {p.background_medium};
        color: {p.foreground_dim};
        padding: 4px 10px;
        border: 1px solid {p.background_light};
    }}
    QTabBar::tab:selected {{
        background-color: {p.background_light};
        color: {p.amber_bright};
        border-bottom-color: {p.amber_primary};
    }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background-color: {p.background_medium};
        border: none;
    }}
    QScrollBar::handle {{
        background-color: {p.background_light};
        border-radius: 3px;
    }}
    QScrollBar::handle:hover {{
        background-color: {p.amber_primary};
    }}
    QSplitter::handle {{
        background-color: {p.background_light};
    }}
    """
