from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui.editor.grid_editor_widgets import GlowIconButton, make_separator, make_status_chip
from src.ui.style import theme

if TYPE_CHECKING:
    from src.ui.editor.grid_editor import GridEditor


def build_controls(editor: GridEditor) -> None:
    editor._ctrl_bar = QWidget()
    editor._ctrl_bar.setObjectName("controlBar")
    bar = QHBoxLayout(editor._ctrl_bar)
    bar.setContentsMargins(18, 0, 18, 0)
    bar.setSpacing(10)

    warn_color = QColor(theme.WARNING)
    danger_color = QColor(theme.ERROR)

    modes = [
        ("h-line.svg", "add_h", "Add a horizontal row boundary. Click-drag across the page."),
        ("v-line.svg", "add_v", "Add a vertical column boundary. Click-drag across the page."),
        ("link.svg", "grouping", "Create a group by clicking cells in field order."),
        ("omit-area.svg", "omit", "Ignore an area on this page. Click-drag the region to skip."),
    ]
    for icon_name, mode, tooltip in modes:
        glow = QColor(warn_color) if mode == "omit" else None
        btn = GlowIconButton(icon_name, tooltip, glow_color=glow, checkable=True)
        if mode == "omit":
            btn.setProperty("warn", True)
        btn.clicked.connect(lambda _checked, m=mode, b=btn: editor._set_mode(m, b))
        setattr(editor, f"_btn_{mode}", btn)
        bar.addWidget(btn)

    bar.addSpacing(6)
    bar.addWidget(make_separator())
    bar.addSpacing(6)

    editor._fields_btn = GlowIconButton(
        "layers.svg",
        "Define extraction fields, types, click counts, and column order.",
    )
    editor._fields_btn.clicked.connect(editor._edit_fields)
    bar.addWidget(editor._fields_btn)

    bar.addSpacing(6)
    bar.addWidget(make_separator())
    bar.addSpacing(6)

    editor._prev_page_btn = GlowIconButton("chevron-left.svg", "Previous page")
    editor._prev_page_btn.clicked.connect(lambda: editor._go_to_page(editor.current_page_index() - 1))
    bar.addWidget(editor._prev_page_btn)

    editor._page_label = make_status_chip("—/—")
    editor._page_label.setToolTip("Current page")
    bar.addWidget(editor._page_label)

    editor._next_page_btn = GlowIconButton("chevron-right.svg", "Next page")
    editor._next_page_btn.clicked.connect(lambda: editor._go_to_page(editor.current_page_index() + 1))
    bar.addWidget(editor._next_page_btn)

    bar.addSpacing(8)

    editor._seg_prev_btn = GlowIconButton("chevrons-left.svg", "Previous layout segment")
    editor._seg_prev_btn.setEnabled(False)
    editor._seg_prev_btn.clicked.connect(editor._on_nav_prev_segment)
    bar.addWidget(editor._seg_prev_btn)

    editor._seg_label = make_status_chip("—")
    editor._seg_label.setToolTip("Current layout segment")
    bar.addWidget(editor._seg_label)

    editor._seg_next_btn = GlowIconButton("chevrons-right.svg", "Next layout segment")
    editor._seg_next_btn.setEnabled(False)
    editor._seg_next_btn.clicked.connect(editor._on_nav_next_segment)
    bar.addWidget(editor._seg_next_btn)

    bar.addSpacing(8)

    editor._zoom_label = make_status_chip("100%")
    editor._zoom_label.setToolTip("Zoom level — scroll over the page to zoom")
    bar.addWidget(editor._zoom_label)

    bar.addStretch(1)

    bar.addWidget(make_separator())
    bar.addSpacing(6)

    editor._omit_page_btn = GlowIconButton(
        "page-omit.svg",
        "Omit this page from extraction.",
        glow_color=warn_color,
        checkable=True,
    )
    editor._omit_page_btn.setProperty("warn", True)
    editor._omit_page_btn.clicked.connect(editor._toggle_current_page_omitted)
    bar.addWidget(editor._omit_page_btn)

    omit_all_btn = GlowIconButton(
        "pages-omit.svg",
        "Omit every page so none are extracted.",
        glow_color=warn_color,
    )
    omit_all_btn.setProperty("warn", True)
    omit_all_btn.clicked.connect(editor._omit_all_pages)
    bar.addWidget(omit_all_btn)

    bar.addSpacing(6)
    bar.addWidget(make_separator())
    bar.addSpacing(6)

    clear_btn = GlowIconButton(
        "trash.svg",
        "Clear all lines, groups, and omissions for this PDF.",
        glow_color=danger_color,
    )
    clear_btn.setProperty("danger", True)
    clear_btn.clicked.connect(editor._clear_grid)
    bar.addWidget(clear_btn)


def build_empty_state(on_open_requested: Callable[[], None]) -> QWidget:
    widget = QWidget()
    inner = QVBoxLayout(widget)
    inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.setSpacing(0)

    icon_label = QLabel()
    pix = QPixmap(theme.icon_path("document.svg"))
    if not pix.isNull():
        icon_label.setPixmap(
            pix.scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.addWidget(icon_label)
    inner.addSpacing(22)

    title = QLabel("Open a PDF to begin")
    title.setProperty("heading", True)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.addWidget(title)
    inner.addSpacing(8)

    subtitle = QLabel("Define reusable row and column boundaries, then group fields for export.")
    subtitle.setProperty("body", True)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.addWidget(subtitle)
    inner.addSpacing(28)

    open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
    open_btn.setProperty("primary", True)
    open_btn.setFixedWidth(170)
    open_btn.clicked.connect(on_open_requested)
    inner.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    return widget


