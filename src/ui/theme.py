"""Modern dark-theme design tokens and global QSS stylesheet.

Keep UI colors centralized here so widgets stay visually consistent and the
application keeps a polished, production-dashboard feel.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG_BASE = "#0B1120"
BG_APP = "#0F172A"
BG_SURFACE = "#111827"
BG_SURFACE_ALT = "#162033"
BG_ELEVATED = "#1E293B"
BG_ELEVATED_SOFT = "#243044"
BG_HOVER = "#2A3A52"
BG_ACTIVE = "#334155"

BORDER = "#263244"
BORDER_LIGHT = "#3B4A61"
BORDER_STRONG = "#526178"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#94A3B8"
TEXT_DISABLED = "#64748B"

ACCENT = "#38BDF8"
ACCENT_HOVER = "#0EA5E9"
ACCENT_PRESSED = "#0284C7"
ACCENT_SOFT = "rgba(56, 189, 248, 0.14)"
ACCENT_TEXT = "#03121F"

SUCCESS = "#22C55E"
ERROR = "#F43F5E"
WARNING = "#F59E0B"

GRID_LINE = "#050505"
GRID_LINE_ACTIVE = "#000000"
GRID_LINE_SOFT = "rgba(0, 0, 0, 0.12)"
GRID_HANDLE = "#F8FAFC"
GRID_HANDLE_INNER = "#050505"
PAIR_IMAGE = "rgba(56, 189, 248, 0.18)"
PAIR_TEXT = "rgba(34, 197, 94, 0.16)"
PAIR_PENDING = "rgba(245, 158, 11, 0.24)"
PAIR_HOVER = "rgba(148, 163, 184, 0.16)"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_FAMILY = "Inter, Segoe UI, system-ui, sans-serif"
FONT_SM = 11
FONT_MD = 13
FONT_LG = 16
FONT_XL = 20

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
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}

QMainWindow, QDialog {{
    background-color: {BG_BASE};
}}

QWidget#workspace {{
    background-color: {BG_BASE};
}}

/* ── Top action bar ─────────────────────────────────────────────────────── */
QWidget#actionBar {{
    background-color: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
    min-height: 58px;
    max-height: 58px;
}}

QWidget#actionBar QLabel {{
    background-color: transparent;
}}

QLabel#appTitle {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_LG}px;
    font-weight: 700;
}}

QLabel#appSubtitle,
QLabel#toolbarHint,
QLabel#profileHelper,
QLabel#statusText {{
    color: {TEXT_MUTED};
    font-size: {FONT_SM}px;
}}

QWidget#toolbarGroup,
QWidget#profileGroup {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

/* ── Grid editor control bar ────────────────────────────────────────────── */
QWidget#controlBar {{
    background-color: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
    min-height: 54px;
    max-height: 54px;
}}

QWidget#controlBar QLabel {{
    background-color: transparent;
}}

QLabel#toolLabel {{
    color: {TEXT_SECONDARY};
    font-size: {FONT_SM}px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton,
QToolButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 9px;
    padding: 7px 13px;
    min-height: 18px;
    font-size: {FONT_MD}px;
    font-weight: 600;
}}

QPushButton:hover,
QToolButton:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
    border-color: {BORDER_STRONG};
}}

QPushButton:pressed,
QToolButton:pressed {{
    background-color: {BG_ACTIVE};
}}

QPushButton:disabled,
QToolButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER};
    background-color: {BG_SURFACE_ALT};
}}

QPushButton[primary="true"],
QToolButton[primary="true"] {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
    border-color: {ACCENT};
    font-weight: 700;
}}

QPushButton[primary="true"]:hover,
QToolButton[primary="true"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton[primary="true"]:pressed,
QToolButton[primary="true"]:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}

QPushButton[ghost="true"],
QToolButton[ghost="true"] {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QPushButton[ghost="true"]:hover,
QToolButton[ghost="true"]:hover {{
    background-color: rgba(244, 63, 94, 0.10);
    color: {ERROR};
    border-color: rgba(244, 63, 94, 0.45);
}}

QToolButton::menu-indicator {{
    image: none;
    width: 0px;
}}

/* ── Segmented control ──────────────────────────────────────────────────── */
QWidget#segmentedControl {{
    background-color: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}}

QWidget#segmentedControl QPushButton {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-radius: 7px;
    padding: 7px 12px;
    min-width: 86px;
    font-size: {FONT_MD}px;
    font-weight: 700;
}}

QWidget#segmentedControl QPushButton:hover:!checked {{
    background-color: rgba(148, 163, 184, 0.10);
    color: {TEXT_PRIMARY};
    border: none;
}}

QWidget#segmentedControl QPushButton:checked {{
    background-color: rgba(56, 189, 248, 0.12);
    color: {ACCENT};
    border: none;
}}

/* ── Menus / dropdowns ──────────────────────────────────────────────────── */
QMenu {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    background-color: transparent;
    border-radius: 7px;
    padding: 8px 26px 8px 10px;
}}

QMenu::item:selected {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

QMenu::item:disabled {{
    color: {TEXT_DISABLED};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 6px 4px;
}}

/* ── ComboBox / inputs ──────────────────────────────────────────────────── */
QComboBox,
QLineEdit {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 9px;
    padding: 7px 10px;
    font-size: {FONT_MD}px;
    min-width: 170px;
}}

QComboBox:hover,
QLineEdit:hover {{
    border-color: {BORDER_STRONG};
}}

QComboBox:focus,
QLineEdit:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 24px;
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {BG_HOVER};
    selection-color: {TEXT_PRIMARY};
    outline: none;
    padding: 4px;
}}

/* ── PDF viewer ─────────────────────────────────────────────────────────── */
QWidget#pdfViewer {{
    background-color: {BG_BASE};
}}

QLabel#pdfPageLabel {{
    background-color: {BG_BASE};
    border: none;
}}

/* ── Preview panel ─────────────────────────────────────────────────────── */
QWidget#previewPanel {{
    background-color: {BG_SURFACE};
    border-left: 1px solid {BORDER};
}}

QLabel#panelTitle {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_LG}px;
    font-weight: 700;
}}

QLabel#panelSummary {{
    color: {TEXT_MUTED};
    font-size: {FONT_MD}px;
}}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {BG_BASE};
    alternate-background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 12px;
    gridline-color: {BORDER};
    font-size: {FONT_MD}px;
    outline: none;
}}

QTableWidget::item {{
    padding: 7px 9px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: rgba(56, 189, 248, 0.14);
    color: {TEXT_PRIMARY};
}}

QHeaderView {{
    background-color: {BG_ELEVATED};
}}

QHeaderView::section {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 8px 10px;
    font-size: {FONT_SM}px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.7px;
}}

QTableCornerButton::section {{
    background-color: {BG_ELEVATED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
}}

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    border: none;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER_LIGHT};
    border-radius: 5px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {BORDER_STRONG};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    border: none;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER_LIGHT};
    border-radius: 5px;
    min-width: 28px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {BORDER_STRONG};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Labels ─────────────────────────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    color: {TEXT_MUTED};
    font-size: {FONT_SM}px;
}}

QLabel[heading="true"] {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_XL}px;
    font-weight: 800;
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


/* ── Extraction progress ───────────────────────────────────────────────── */
QProgressBar#extractProgress {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    min-height: 10px;
    max-height: 10px;
}}

QProgressBar#extractProgress::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}
"""


