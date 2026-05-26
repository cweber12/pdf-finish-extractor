from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.editor.grid_editor_widgets import GlowIconButton, make_separator, make_status_chip
from src.ui.style import theme

if TYPE_CHECKING:
    from src.ui.editor.pattern_editor import PatternEditor


def build_pattern_controls(editor: PatternEditor) -> None:
    editor._ctrl_bar = QWidget()
    editor._ctrl_bar.setObjectName("controlBar")
    bar = QHBoxLayout(editor._ctrl_bar)
    bar.setContentsMargins(18, 0, 18, 0)
    bar.setSpacing(10)

    warn_color = QColor(theme.WARNING)
    danger_color = QColor(theme.ERROR)

    # Crop Image mode toggle
    editor._btn_crop = GlowIconButton(
        "omit-area.svg",
        "Crop Image — click-drag on the page to define the reference swatch rectangle.",
        checkable=True,
    )
    editor._btn_crop.clicked.connect(
        lambda _checked, b=editor._btn_crop: editor._set_mode("crop_image", b)
    )
    bar.addWidget(editor._btn_crop)

    # Omit area mode toggle
    editor._btn_omit = GlowIconButton(
        "omit-area.svg",
        "Omit Area — click-drag to mark a region to skip during detection.",
        glow_color=warn_color,
        checkable=True,
    )
    editor._btn_omit.setProperty("warn", True)
    editor._btn_omit.clicked.connect(
        lambda _checked, b=editor._btn_omit: editor._set_mode("omit", b)
    )
    bar.addWidget(editor._btn_omit)

    bar.addSpacing(6)
    bar.addWidget(make_separator())
    bar.addSpacing(6)

    # Text Side dropdown
    side_label = QLabel("Side:")
    side_label.setProperty("body", True)
    bar.addWidget(side_label)

    editor._text_side_btn = QToolButton()
    editor._text_side_btn.setObjectName("textSideButton")
    editor._text_side_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    editor._text_side_btn.setToolTip("Side of the image where the text region is located.")
    editor._text_side_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    editor._text_side_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    side_menu = QMenu(editor._text_side_btn)
    for side_name, side_id in (("Below", "below"), ("Above", "above"), ("Right", "right"), ("Left", "left")):
        action = side_menu.addAction(side_name)
        action.triggered.connect(lambda _checked, s=side_id: editor._on_text_side_changed(s))
    editor._text_side_btn.setMenu(side_menu)
    editor._text_side_btn.setText("Below ▾")
    bar.addWidget(editor._text_side_btn)

    bar.addSpacing(8)

    # Sections spinner
    sections_label = QLabel("Sections:")
    sections_label.setProperty("body", True)
    bar.addWidget(sections_label)

    editor._sections_spin = QSpinBox()
    editor._sections_spin.setObjectName("sectionsSpinner")
    editor._sections_spin.setRange(1, 6)
    editor._sections_spin.setValue(1)
    editor._sections_spin.setToolTip("Number of text sections adjacent to the image (1–6).")
    editor._sections_spin.setFixedWidth(52)
    editor._sections_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    editor._sections_spin.valueChanged.connect(editor._on_section_count_changed)
    bar.addWidget(editor._sections_spin)

    bar.addSpacing(8)

    # Rows / Columns segmentation toggle
    seg_label = QLabel("Split:")
    seg_label.setProperty("body", True)
    bar.addWidget(seg_label)

    editor._btn_rows = QPushButton("Rows")
    editor._btn_rows.setObjectName("segBtnLeft")
    editor._btn_rows.setCheckable(True)
    editor._btn_rows.setChecked(True)
    editor._btn_rows.setToolTip("Split text sections into horizontal rows.")
    editor._btn_rows.setCursor(Qt.CursorShape.PointingHandCursor)
    editor._btn_rows.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    editor._btn_rows.clicked.connect(lambda: editor._on_segmentation_changed("rows"))
    bar.addWidget(editor._btn_rows)

    editor._btn_cols = QPushButton("Cols")
    editor._btn_cols.setObjectName("segBtnRight")
    editor._btn_cols.setCheckable(True)
    editor._btn_cols.setToolTip("Split text sections into vertical columns.")
    editor._btn_cols.setCursor(Qt.CursorShape.PointingHandCursor)
    editor._btn_cols.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    editor._btn_cols.clicked.connect(lambda: editor._on_segmentation_changed("columns"))
    bar.addWidget(editor._btn_cols)

    bar.addSpacing(6)

    # Field Names button
    editor._field_names_btn = GlowIconButton(
        "layers.svg",
        "Edit field names for each text section.",
    )
    editor._field_names_btn.clicked.connect(editor._on_edit_field_names)
    bar.addWidget(editor._field_names_btn)

    bar.addSpacing(8)

    editor._apply_pattern_btn = QPushButton(QIcon(theme.icon_path("play.svg")), " Apply Pattern")
    editor._apply_pattern_btn.setObjectName("applyPatternButton")
    editor._apply_pattern_btn.setProperty("primary", True)
    editor._apply_pattern_btn.setToolTip(
        "Save this pattern and return to Manual Grid so you can extract."
    )
    editor._apply_pattern_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    editor._apply_pattern_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    editor._apply_pattern_btn.clicked.connect(editor.apply_requested.emit)
    bar.addWidget(editor._apply_pattern_btn)

    bar.addSpacing(6)
    bar.addWidget(make_separator())
    bar.addSpacing(6)

    # Page navigation
    editor._prev_page_btn = GlowIconButton("chevron-left.svg", "Previous page")
    editor._prev_page_btn.clicked.connect(
        lambda: editor._go_to_page(editor.current_page_index() - 1)
    )
    bar.addWidget(editor._prev_page_btn)

    editor._page_label = make_status_chip("—/—")
    editor._page_label.setToolTip("Current page")
    bar.addWidget(editor._page_label)

    editor._next_page_btn = GlowIconButton("chevron-right.svg", "Next page")
    editor._next_page_btn.clicked.connect(
        lambda: editor._go_to_page(editor.current_page_index() + 1)
    )
    bar.addWidget(editor._next_page_btn)

    bar.addSpacing(8)

    editor._zoom_label = make_status_chip("100%")
    editor._zoom_label.setToolTip("Zoom level — scroll over the page to zoom")
    bar.addWidget(editor._zoom_label)

    bar.addStretch(1)

    bar.addWidget(make_separator())
    bar.addSpacing(6)

    # Omit current page
    editor._omit_page_btn = GlowIconButton(
        "page-omit.svg",
        "Omit this page from detection.",
        glow_color=warn_color,
        checkable=True,
    )
    editor._omit_page_btn.setProperty("warn", True)
    editor._omit_page_btn.clicked.connect(editor._toggle_current_page_omitted)
    bar.addWidget(editor._omit_page_btn)

    omit_all_btn = GlowIconButton(
        "pages-omit.svg",
        "Omit every page so none are detected.",
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
        "Clear the image crop, text region, and all omissions.",
        glow_color=danger_color,
    )
    clear_btn.setProperty("danger", True)
    clear_btn.clicked.connect(editor._clear_pattern)
    bar.addWidget(clear_btn)


def build_pattern_empty_state(on_open_requested: Callable[[], None]) -> QWidget:
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

    subtitle = QLabel(
        "Crop a reference swatch image and configure adjacent text sections for automatic detection."
    )
    subtitle.setProperty("body", True)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    inner.addWidget(subtitle)
    inner.addSpacing(28)

    open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
    open_btn.setProperty("primary", True)
    open_btn.setFixedWidth(170)
    open_btn.clicked.connect(on_open_requested)
    inner.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    return widget
