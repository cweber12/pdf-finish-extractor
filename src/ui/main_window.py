from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme
from src.ui.grid_editor import GridEditor
from src.ui.preview_panel import PreviewPanel
from src.ui.profile_manager import ProfileManager
from src.ui.toast import Toast


def _vline() -> QFrame:
    """Thin vertical separator for compact toolbar groups."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedHeight(28)
    return line


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Finish Extractor")
        self.resize(1280, 900)

        self._profile_manager = ProfileManager()
        self._selected_profile_name: str | None = None
        self._build_central()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_central(self) -> None:
        central = QWidget()
        central.setObjectName("workspace")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_action_bar())

        content = QWidget()
        content.setObjectName("workspace")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._grid_editor = GridEditor()
        self._grid_editor.open_requested.connect(self._on_open_pdf)
        content_layout.addWidget(self._grid_editor, stretch=3)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        content_layout.addWidget(sep)

        self._preview_panel = PreviewPanel()
        self._preview_panel.setVisible(False)
        content_layout.addWidget(self._preview_panel, stretch=2)

        root.addWidget(content, stretch=1)

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("actionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Brand/title group.
        title_group = QWidget()
        title_group.setObjectName("toolbarGroup")
        title_layout = QHBoxLayout(title_group)
        title_layout.setContentsMargins(12, 6, 12, 6)
        title_layout.setSpacing(10)

        title_icon = QLabel()
        pix = QIcon(theme.icon_path("document.svg")).pixmap(22, 22)
        title_icon.setPixmap(pix)
        title_layout.addWidget(title_icon)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(0)
        app_title = QLabel("PDF Finish Extractor")
        app_title.setObjectName("appTitle")
        app_subtitle = QLabel("Grid profiles • swatch extraction • upload review")
        app_subtitle.setObjectName("appSubtitle")
        title_stack.addWidget(app_title)
        title_stack.addWidget(app_subtitle)
        title_layout.addLayout(title_stack)
        layout.addWidget(title_group)

        # File action.
        open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
        open_btn.setToolTip("Open a PDF and start defining extraction boundaries.")
        open_btn.clicked.connect(self._on_open_pdf)
        layout.addWidget(open_btn)

        layout.addWidget(_vline())

        # Profile dropdown/action group.
        profile_group = QWidget()
        profile_group.setObjectName("profileGroup")
        profile_layout = QHBoxLayout(profile_group)
        profile_layout.setContentsMargins(10, 5, 10, 5)
        profile_layout.setSpacing(8)

        profile_text = QVBoxLayout()
        profile_text.setContentsMargins(0, 0, 0, 0)
        profile_text.setSpacing(0)
        profile_label = QLabel("Profile")
        profile_label.setObjectName("toolLabel")
        self._profile_helper = QLabel("Save line + pairing sets for similar PDFs")
        self._profile_helper.setObjectName("profileHelper")
        profile_text.addWidget(profile_label)
        profile_text.addWidget(self._profile_helper)
        profile_layout.addLayout(profile_text)

        self._profile_button = QToolButton()
        self._profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._profile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._profile_button.setIcon(QIcon(theme.icon_path("save.svg")))
        self._profile_button.setText("No profile selected  ▾")
        self._profile_button.setToolTip("Load a saved grid profile or save the current one.")
        self._profile_menu = QMenu(self._profile_button)
        self._profile_button.setMenu(self._profile_menu)
        profile_layout.addWidget(self._profile_button)

        save_btn = QPushButton(QIcon(theme.icon_path("save.svg")), "  Save Current")
        save_btn.setToolTip("Save the current grid lines and cell pairings as a reusable PDF profile.")
        save_btn.clicked.connect(self._on_save_profile)
        profile_layout.addWidget(save_btn)

        layout.addWidget(profile_group)
        self._refresh_profiles()

        layout.addWidget(_vline())

        extract_btn = QPushButton(QIcon(theme.icon_path("play.svg")), "  Extract All Pages")
        extract_btn.setProperty("primary", True)
        extract_btn.setToolTip("Run extraction using the current grid and pairings.")
        extract_btn.clicked.connect(self._on_extract)
        layout.addWidget(extract_btn)

        layout.addStretch()

        self._status_label = QLabel("Open a PDF to begin.")
        self._status_label.setObjectName("statusText")
        layout.addWidget(self._status_label)
        return bar

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._grid_editor.load_pdf(path)
            self._preview_panel.setVisible(False)
            self._status_label.setText("PDF loaded. Define or apply a grid profile.")

    def _on_profile_selected(self, name: str) -> None:
        profile = self._profile_manager.load(name)
        if profile:
            self._grid_editor.apply_profile(profile)
            self._selected_profile_name = name
            self._profile_button.setText(f"{name}  ▾")
            self._profile_helper.setText("Profile applied to the current PDF")
            self._status_label.setText(f"Profile applied: {name}")
            Toast.show_in(self.window(), f"Profile applied: {name}", success=True)

    def _on_save_profile(self) -> None:
        profile = self._grid_editor.current_profile()
        if profile is None:
            Toast.show_in(
                self.window(),
                "Add at least one grid line before saving a profile.",
                success=False,
            )
            return

        suggested = self._selected_profile_name or ""
        name, ok = QInputDialog.getText(
            self,
            "Save PDF Profile",
            "Profile name:",
            text=suggested,
        )
        if not ok:
            return

        try:
            saved_name = self._profile_manager.save(name, profile)
        except ValueError as exc:
            Toast.show_in(self.window(), str(exc), success=False)
            return

        self._selected_profile_name = saved_name
        self._refresh_profiles()
        self._profile_button.setText(f"{saved_name}  ▾")
        self._profile_helper.setText("Current grid saved for reuse")
        self._status_label.setText(f"Profile saved: {saved_name}")
        Toast.show_in(self.window(), f"Profile saved: {saved_name}", success=True)

    def _on_extract(self) -> None:
        profile = self._grid_editor.current_profile()
        pdf_path = self._grid_editor.pdf_path
        if not pdf_path:
            Toast.show_in(self.window(), "Open a PDF before extracting.", success=False)
            return
        if not profile:
            Toast.show_in(self.window(), "Create or apply a grid profile before extracting.", success=False)
            return

        from src.extraction.extractor import Extractor

        self._status_label.setText("Extracting all pages…")
        pairs = Extractor(pdf_path, profile).extract_all_pages()
        self._preview_panel.load(pairs)
        self._preview_panel.setVisible(True)
        self._status_label.setText(f"Extraction complete: {len(pairs)} pairs found.")

    def _refresh_profiles(self) -> None:
        if not hasattr(self, "_profile_menu"):
            return

        self._profile_menu.clear()
        profile_names = self._profile_manager.list_profiles()

        if not profile_names:
            empty_action = QAction("No saved profiles yet", self)
            empty_action.setEnabled(False)
            self._profile_menu.addAction(empty_action)
        else:
            for name in profile_names:
                action = QAction(name, self)
                action.triggered.connect(lambda _checked=False, n=name: self._on_profile_selected(n))
                self._profile_menu.addAction(action)

        self._profile_menu.addSeparator()
        save_action = QAction("Save current grid as profile…", self)
        save_action.triggered.connect(self._on_save_profile)
        self._profile_menu.addAction(save_action)
