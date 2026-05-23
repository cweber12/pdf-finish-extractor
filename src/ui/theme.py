"""Modern dark-theme design tokens and global QSS stylesheet.

The UI leans on Qt's layout system, plain widgets, and centralized styling so
visual polish stays separate from extraction and upload behavior.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG_BASE = "#080E1A"
BG_APP = "#0D1626"
BG_SURFACE = "#111C2E"
BG_SURFACE_ALT = "#162235"
BG_ELEVATED = "#1B2A41"
BG_ELEVATED_SOFT = "#22324B"
BG_HOVER = "#2A3D59"
BG_ACTIVE = "#314766"
BG_PANEL = "#0B1322"

BORDER = "#223148"
BORDER_LIGHT = "#344762"
BORDER_STRONG = "#526987"
BORDER_SUBTLE = "#19263A"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#D7E0EE"
TEXT_MUTED = "#94A3B8"
TEXT_DISABLED = "#64748B"

ACCENT = "#38BDF8"
ACCENT_HOVER = "#0EA5E9"
ACCENT_PRESSED = "#0284C7"
ACCENT_SOFT = "rgba(56, 189, 248, 0.12)"
ACCENT_TEXT = "#03121F"

SUCCESS = "#22C55E"
ERROR = "#F43F5E"
WARNING = "#F59E0B"

GRID_LINE = "#030303"
GRID_LINE_ACTIVE = "#000000"
GRID_LINE_SOFT = "rgba(0, 0, 0, 0.14)"
GRID_HANDLE = "#F8FAFC"
GRID_HANDLE_HOVER = "#E0F2FE"
GRID_HANDLE_INNER = "#050505"
GRID_HANDLE_RAIL = "rgba(15, 23, 42, 0.38)"
PAIR_IMAGE = "rgba(56, 189, 248, 0.15)"
PAIR_TEXT = "rgba(34, 197, 94, 0.14)"
PAIR_PENDING = "rgba(245, 158, 11, 0.24)"
PAIR_HOVER = "rgba(148, 163, 184, 0.14)"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# Uses installed system fonts first. No bundled font files are required.
FONT_FAMILY = "Aptos, Segoe UI Variable, Segoe UI, Inter, Arial, sans-serif"
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
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT_PRIMARY};
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
    min-height: 64px;
    max-height: 64px;
}}

QWidget#actionBar QLabel {{
    background-color: transparent;
}}

QWidget#brandCluster,
QWidget#brandText {{
    background-color: transparent;
    border: none;
}}

QLabel#brandMark {{
    background-color: transparent;
    border: none;
}}

QLabel#appTitle {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.2px;
}}

QLabel#appSubtitle {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}}

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

QWidget#topActionCluster {{
    background-color: transparent;
    border: none;
}}

/* Grid Layouts dropdown — square edges, flush with the bottom of the bar */
QToolButton#layoutsDropdown {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 0;
    padding: 0 14px 0 12px;
    min-height: 63px;
    max-height: 63px;
    min-width: 210px;
    font-size: {FONT_MD}px;
    font-weight: 650;
    letter-spacing: 0.2px;
}}

QToolButton#layoutsDropdown:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
    border-color: {BORDER_LIGHT};
}}

QToolButton#layoutsDropdown:pressed,
QToolButton#layoutsDropdown:on {{
    background-color: {BG_ACTIVE};
    border-color: {ACCENT};
}}

QToolButton#layoutsDropdown::menu-indicator {{
    image: none;
    width: 0;
}}

QToolButton#layoutsDropdown[hasSelection="true"] {{
    border-top: 2px solid {ACCENT};
    background-color: {BG_ELEVATED_SOFT};
}}

/* Extract primary action — the action bar's hero icon button. */
QToolButton#extractButton {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    border-radius: 9px;
    min-width: 44px;
    max-width: 44px;
    min-height: 34px;
    max-height: 34px;
    padding: 4px 6px;
}}

QToolButton#extractButton:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QToolButton#extractButton:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}

QToolButton#extractButton:disabled {{
    background-color: {BG_ELEVATED_SOFT};
    border-color: {BORDER};
}}

QLabel#statusChipBar {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: {FONT_SM}px;
    font-weight: 600;
    letter-spacing: 0.2px;
    padding: 0 4px;
}}

/* ── Grid editor control bar ────────────────────────────────────────────── */
QWidget#controlBar {{
    background-color: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
    min-height: 52px;
    max-height: 52px;
}}

QWidget#controlBar QLabel {{
    background-color: transparent;
}}

QWidget#toolGroup {{
    background-color: transparent;
    border: none;
}}

QFrame#toolbarSeparator {{
    background-color: {BORDER};
    border: none;
    max-width: 1px;
    min-width: 1px;
}}

QLabel.statusChip {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-family: "JetBrains Mono", "Consolas", "Cascadia Mono", monospace;
    font-size: {FONT_SM}px;
    font-weight: 700;
    letter-spacing: 0.3px;
    padding: 0 6px;
    min-width: 38px;
}}

QLabel.statusChip[muted="true"] {{
    color: {TEXT_DISABLED};
}}

QToolButton.iconAction {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
}}

QToolButton.iconAction:hover {{
    background-color: rgba(56, 189, 248, 0.10);
    border: 1px solid rgba(56, 189, 248, 0.35);
}}

QToolButton.iconAction:pressed {{
    background-color: rgba(56, 189, 248, 0.20);
    border: 1px solid rgba(56, 189, 248, 0.55);
}}

QToolButton.iconAction:checked {{
    background-color: rgba(56, 189, 248, 0.18);
    border: 1px solid rgba(56, 189, 248, 0.55);
}}

QToolButton.iconAction:disabled {{
    background-color: transparent;
    border: 1px solid transparent;
}}

QToolButton.iconAction[danger="true"]:hover {{
    background-color: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.45);
}}

QToolButton.iconAction[danger="true"]:pressed {{
    background-color: rgba(244, 63, 94, 0.22);
    border: 1px solid rgba(244, 63, 94, 0.60);
}}

QToolButton.iconAction[warn="true"]:checked {{
    background-color: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.55);
}}

QToolButton.iconAction[warn="true"]:hover {{
    background-color: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.45);
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton,
QToolButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 9px;
    padding: 7px 13px;
    min-height: 20px;
    font-size: {FONT_MD}px;
    font-weight: 650;
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
    font-weight: 750;
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

/* ── Splitter / workspace ───────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:hover {{
    background-color: {BORDER_LIGHT};
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
    font-weight: 750;
}}

QLabel#panelSummary {{
    color: {TEXT_MUTED};
    font-size: {FONT_MD}px;
}}

QWidget#previewTableFrame {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: transparent;
    alternate-background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 0;
    gridline-color: {BORDER};
    font-size: {FONT_MD}px;
    outline: none;
}}

QTableWidget::item {{
    padding: 7px 9px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: rgba(56, 189, 248, 0.10);
    color: {TEXT_PRIMARY};
}}

QTableWidget::item:focus {{
    border: none;
    outline: none;
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

QHeaderView::section:last {{
    border-right: none;
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




