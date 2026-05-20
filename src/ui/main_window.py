from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme
from src.ui.grid_editor import GridEditor
from src.ui.preview_panel import PreviewPanel
from src.ui.profile_manager import ProfileManager


def _vline() -> QFrame:
    """Thin vertical separator for the action bar."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedHeight(22)
    return line


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Finish Extractor")
        self.resize(1280, 900)

        self._profile_manager = ProfileManager()
        self._build_central()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_action_bar())

        content = QWidget()
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
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        # File group
        open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
        open_btn.clicked.connect(self._on_open_pdf)
        layout.addWidget(open_btn)

        layout.addWidget(_vline())

        # Profile group
        profile_label = QLabel("Profile")
        profile_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(profile_label)

        self._profile_combo = QComboBox()
        self._refresh_profiles()
        self._profile_combo.currentTextChanged.connect(self._on_profile_selected)
        layout.addWidget(self._profile_combo)

        save_btn = QPushButton(QIcon(theme.icon_path("save.svg")), "  Save")
        save_btn.clicked.connect(self._on_save_profile)
        layout.addWidget(save_btn)

        layout.addWidget(_vline())

        # Extract group
        extract_btn = QPushButton(QIcon(theme.icon_path("play.svg")), "  Extract All Pages")
        extract_btn.setProperty("primary", True)
        extract_btn.clicked.connect(self._on_extract)
        layout.addWidget(extract_btn)

        layout.addStretch()
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

    def _on_profile_selected(self, name: str) -> None:
        profile = self._profile_manager.load(name)
        if profile:
            self._grid_editor.apply_profile(profile)

    def _on_save_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if ok and name.strip():
            profile = self._grid_editor.current_profile()
            self._profile_manager.save(name.strip(), profile)
            self._refresh_profiles()

    def _on_extract(self) -> None:
        profile = self._grid_editor.current_profile()
        pdf_path = self._grid_editor.pdf_path
        if not pdf_path or not profile:
            return

        from src.extraction.extractor import Extractor

        pairs = Extractor(pdf_path, profile).extract_all_pages()
        self._preview_panel.load(pairs)
        self._preview_panel.setVisible(True)

    def _refresh_profiles(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItem("")
        for name in self._profile_manager.list_profiles():
            self._profile_combo.addItem(name)
        self._profile_combo.blockSignals(False)
