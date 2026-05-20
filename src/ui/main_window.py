from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QToolBar,
    QWidget,
)

from src.ui.grid_editor import GridEditor
from src.ui.preview_panel import PreviewPanel
from src.ui.profile_manager import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Finish Extractor")
        self.resize(1280, 900)

        self._profile_manager = ProfileManager()
        self._build_toolbar()
        self._build_central()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        self.addToolBar(toolbar)

        open_btn = QPushButton("Open PDF")
        open_btn.clicked.connect(self._on_open_pdf)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(180)
        self._refresh_profiles()
        self._profile_combo.currentTextChanged.connect(self._on_profile_selected)
        toolbar.addWidget(self._profile_combo)

        save_profile_btn = QPushButton("Save Profile")
        save_profile_btn.clicked.connect(self._on_save_profile)
        toolbar.addWidget(save_profile_btn)

        toolbar.addSeparator()

        extract_btn = QPushButton("Extract All Pages")
        extract_btn.clicked.connect(self._on_extract)
        toolbar.addWidget(extract_btn)

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self._grid_editor = GridEditor()
        layout.addWidget(self._grid_editor, stretch=3)

        self._preview_panel = PreviewPanel()
        self._preview_panel.setVisible(False)
        layout.addWidget(self._preview_panel, stretch=2)

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
