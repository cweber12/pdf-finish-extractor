"""Dark-theme design tokens and global QSS stylesheet.

All UI components import this module for colours and the STYLESHEET constant.
No hex values should be hardcoded elsewhere in the UI layer.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG_BASE = "#0f1117"
BG_SURFACE = "#1a1c23"
BG_ELEVATED = "#22252e"
BG_HOVER = "#2a2e3a"

BORDER = "#2e3340"
BORDER_LIGHT = "#3a3f4e"

TEXT_PRIMARY = "#f0f2f8"
TEXT_MUTED = "#8b93a7"
TEXT_DISABLED = "#4a5060"

ACCENT = "#06b6d4"
ACCENT_HOVER = "#0891b2"
ACCENT_PRESSED = "#0e7490"
ACCENT_TEXT = "#041d24"  # dark text on teal background

SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#f59e0b"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_FAMILY = "Segoe UI, system-ui, sans-serif"
FONT_SM = 11   # small labels, table headers
FONT_MD = 13   # body, buttons
FONT_LG = 16   # headings

# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")


def icon_path(name: str) -> str:
    """Absolute path to a bundled SVG icon."""
    return os.path.join(ICONS_DIR, name)


# ---------------------------------------------------------------------------
# Global stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ── Base ───────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}

QMainWindow, QDialog {{
    background-color: {BG_BASE};
}}

/* ── Action bar ─────────────────────────────────────────────────────────── */
QWidget#actionBar {{
    background-color: {BG_ELEVATED};
    border-bottom: 1px solid {BORDER};
    min-height: 48px;
    max-height: 48px;
}}

QWidget#actionBar QLabel {{
    color: {TEXT_MUTED};
    font-size: {FONT_SM}px;
    background-color: transparent;
}}

/* ── Control bar (grid editor) ──────────────────────────────────────────── */
QWidget#controlBar {{
    background-color: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
    min-height: 44px;
    max-height: 44px;
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 14px;
    font-size: {FONT_MD}px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_LIGHT};
}}

QPushButton:pressed {{
    background-color: {BG_BASE};
}}

QPushButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER};
    background-color: {BG_SURFACE};
}}

/* Primary / accent button */
QPushButton[primary="true"] {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
    border-color: {ACCENT};
    font-weight: 600;
}}

QPushButton[primary="true"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton[primary="true"]:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}

/* Ghost / destructive button */
QPushButton[ghost="true"] {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QPushButton[ghost="true"]:hover {{
    color: {ERROR};
    border-color: {ERROR};
    background-color: transparent;
}}

/* ── Segmented control ──────────────────────────────────────────────────── */
QWidget#segmentedControl {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QWidget#segmentedControl QPushButton {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-radius: 0;
    padding: 5px 14px;
    font-size: {FONT_MD}px;
    font-weight: 500;
}}

QWidget#segmentedControl QPushButton:last-child {{
    border-right: none;
}}

QWidget#segmentedControl QPushButton:checked {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
    font-weight: 600;
}}

QWidget#segmentedControl QPushButton:hover:!checked {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── ComboBox ───────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    font-size: {FONT_MD}px;
    min-width: 160px;
}}

QComboBox:hover {{
    border-color: {BORDER_LIGHT};
}}

QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 22px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
    outline: none;
    padding: 2px;
}}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {BG_SURFACE};
    alternate-background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    font-size: {FONT_MD}px;
}}

QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: rgba(6, 182, 212, 0.15);
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 5px 8px;
    font-size: {FONT_SM}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:last {{
    border-right: none;
}}

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER_LIGHT};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_DISABLED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER_LIGHT};
    border-radius: 4px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_DISABLED};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    max-height: 6px;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

/* ── Labels ─────────────────────────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    color: {TEXT_MUTED};
    font-size: {FONT_SM}px;
}}

QLabel[heading="true"] {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_LG}px;
    font-weight: 600;
}}

QLabel[body="true"] {{
    color: {TEXT_MUTED};
    font-size: {FONT_MD}px;
}}

/* ── Separator lines ────────────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {BORDER};
}}

/* ── Input fields (dialogs) ─────────────────────────────────────────────── */
QLineEdit {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_MD}px;
}}

QLineEdit:focus {{
    border-color: {ACCENT};
}}
"""
