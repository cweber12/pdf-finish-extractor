from __future__ import annotations

from PyQt6.QtCore import QObject, QSize, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.extraction.extractor import ExtractionProgress, Extractor
from src.extraction.grid import Grid, GridSegment
from src.ui import theme
from src.ui.grid_editor import GlowIconButton, GridEditor
from src.ui.preview_panel import PreviewPanel
from src.ui.profile_manager import ProfileManager
from src.ui.toast import Toast


class _ExtractionWorker(QObject):
    """Runs PDF extraction off the Qt main thread.

    The expensive work is intentionally isolated from the UI. Signals are used
    to report progress and completion back to ``MainWindow`` safely.
    """

    progress = pyqtSignal(int, int, int)  # page_index, page_count, pairs_extracted
    finished = pyqtSignal(object, bool)   # list[ExtractedPair], was_cancelled
    failed = pyqtSignal(str)

    def __init__(self, pdf_path: str, profile: Grid, segments: list[GridSegment]) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._profile = profile
        self._segments = segments
        self._cancel_requested = False

    @pyqtSlot()
    def run(self) -> None:
        """Execute extraction in the worker thread."""
        try:
            def on_progress(progress: ExtractionProgress) -> None:
                self.progress.emit(
                    progress.page_index,
                    progress.page_count,
                    progress.pairs_extracted,
                )

            extractor = Extractor(self._pdf_path, self._profile, segments=self._segments or None)
            pairs = extractor.extract_all_pages(
                progress_callback=on_progress,
                cancel_check=lambda: self._cancel_requested,
            )
            self.finished.emit(pairs, self._cancel_requested)
        except Exception as exc:  # noqa: BLE001 - user-facing extraction failure
            self.failed.emit(str(exc))

    @pyqtSlot()
    def cancel(self) -> None:
        """Request a clean stop between pages."""
        self._cancel_requested = True


def _make_separator() -> QFrame:
    """Thin vertical separator that matches the grid editor's toolbar style."""
    sep = QFrame()
    sep.setObjectName("toolbarSeparator")
    sep.setFrameShape(QFrame.Shape.NoFrame)
    sep.setFixedWidth(1)
    sep.setFixedHeight(28)
    return sep


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Finish Extractor")
        self.resize(1280, 900)

        self._profile_manager = ProfileManager()
        self._selected_profile_name: str | None = None
        self._extraction_thread: QThread | None = None
        self._extraction_worker: _ExtractionWorker | None = None
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

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("workspaceSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(1)

        self._grid_editor = GridEditor()
        self._grid_editor.setMinimumWidth(560)
        self._grid_editor.open_requested.connect(self._on_open_pdf)
        self._splitter.addWidget(self._grid_editor)

        self._preview_panel = PreviewPanel()
        self._preview_panel.setMinimumWidth(420)
        self._preview_panel.setVisible(False)
        self._splitter.addWidget(self._preview_panel)
        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([900, 520])

        root.addWidget(self._grid_editor.ctrl_bar)
        root.addWidget(self._splitter, stretch=1)

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("actionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_brand())

        # File action — icon-only for cohesion with the grid editor.
        self._open_btn = GlowIconButton(
            "folder-open.svg",
            "Open a PDF and start defining extraction boundaries.",
        )
        self._open_btn.clicked.connect(self._on_open_pdf)
        layout.addWidget(self._open_btn)

        layout.addSpacing(6)
        layout.addWidget(_make_separator())
        layout.addSpacing(6)

        # Grid Layouts dropdown — square edges, flush with the bottom of the bar.
        self._profile_button = QToolButton()
        self._profile_button.setObjectName("layoutsDropdown")
        self._profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._profile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._profile_button.setIcon(QIcon(theme.icon_path("layers.svg")))
        self._profile_button.setIconSize(QSize(16, 16))
        self._profile_button.setText("Grid Layouts")
        self._profile_button.setToolTip("Load a saved grid layout or save the current one.")
        self._profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._profile_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._profile_menu = QMenu(self._profile_button)
        self._profile_button.setMenu(self._profile_menu)
        layout.addWidget(self._profile_button, alignment=Qt.AlignmentFlag.AlignBottom)

        self._save_profile_btn = GlowIconButton(
            "save.svg",
            "Save the current grid lines and pairings as a reusable layout.",
        )
        self._save_profile_btn.clicked.connect(self._on_save_profile)
        layout.addWidget(self._save_profile_btn)

        self._refresh_profiles()

        layout.addSpacing(6)
        layout.addWidget(_make_separator())
        layout.addSpacing(6)

        # Extract action — primary icon button with a stronger accent glow.
        self._extract_btn = GlowIconButton(
            "play.svg",
            "Run extraction using the current grid and pairings.",
        )
        self._extract_btn.setObjectName("extractButton")
        self._extract_btn.setIconSize(QSize(22, 22))
        self._extract_btn.clicked.connect(self._on_extract)
        layout.addWidget(self._extract_btn)

        self._cancel_extract_btn = GlowIconButton(
            "close.svg",
            "Cancel extraction after the current page finishes.",
            glow_color=QColor(theme.ERROR),
        )
        self._cancel_extract_btn.setProperty("danger", True)
        self._cancel_extract_btn.clicked.connect(self._on_cancel_extract)
        self._cancel_extract_btn.setVisible(False)
        layout.addWidget(self._cancel_extract_btn)

        layout.addStretch(1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("extractProgress")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(170)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Open a PDF to begin.")
        self._status_label.setObjectName("statusText")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status_label.setMinimumWidth(180)
        self._status_label.setMaximumWidth(340)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._status_label.setToolTip("Open a PDF to begin.")
        layout.addWidget(self._status_label)
        layout.addSpacing(18)
        return bar

    def _build_brand(self) -> QWidget:
        """Logo + title + tagline cluster on the left of the action bar."""
        cluster = QWidget()
        cluster.setObjectName("brandCluster")
        cluster_layout = QHBoxLayout(cluster)
        cluster_layout.setContentsMargins(0, 0, 8, 0)
        cluster_layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("brandMark")
        logo.setFixedSize(34, 34)
        logo.setPixmap(QIcon(theme.icon_path("logo-mark.svg")).pixmap(34, 34))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cluster_layout.addWidget(logo)

        text = QWidget()
        text.setObjectName("brandText")
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        app_title = QLabel("PDF Finish Extractor")
        app_title.setObjectName("appTitle")
        app_subtitle = QLabel("Grid layouts · Swatch extraction · Upload review")
        app_subtitle.setObjectName("appSubtitle")
        text_layout.addWidget(app_title)
        text_layout.addWidget(app_subtitle)
        cluster_layout.addWidget(text)
        return cluster

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_open_pdf(self) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), "Cancel extraction before opening another PDF.", success=False)
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._grid_editor.load_pdf(path)
            self._preview_panel.setVisible(False)
            self._set_status("PDF loaded. Define or apply a grid profile.")

    def _on_profile_selected(self, name: str) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), "Cancel extraction before changing profiles.", success=False)
            return

        profile = self._profile_manager.load(name)
        if profile:
            self._grid_editor.apply_profile(profile)
            self._selected_profile_name = name
            self._set_selected_layout_label(name)
            self._set_status(f"Profile applied: {name}")
            Toast.show_in(self.window(), f"Profile applied: {name}", success=True)

    def _on_save_profile(self) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), "Cancel extraction before saving a profile.", success=False)
            return

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
        self._set_selected_layout_label(saved_name)
        self._set_status(f"Profile saved: {saved_name}")
        Toast.show_in(self.window(), f"Profile saved: {saved_name}", success=True)

    def _set_selected_layout_label(self, name: str | None) -> None:
        """Reflect the active grid layout on the dropdown button."""
        if name:
            self._profile_button.setText(name)
            self._profile_button.setProperty("hasSelection", True)
        else:
            self._profile_button.setText("Grid Layouts")
            self._profile_button.setProperty("hasSelection", False)
        # Re-evaluate the stylesheet so the hasSelection variant takes effect.
        style = self._profile_button.style()
        if style is not None:
            style.unpolish(self._profile_button)
            style.polish(self._profile_button)

    def _on_extract(self) -> None:
        if self._is_extracting():
            return

        profile = self._grid_editor.current_profile()
        pdf_path = self._grid_editor.pdf_path
        if not pdf_path:
            Toast.show_in(self.window(), "Open a PDF before extracting.", success=False)
            return
        if not profile:
            Toast.show_in(self.window(), "Create or apply a grid profile before extracting.", success=False)
            return

        self._preview_panel.setVisible(False)
        self._set_status("Preparing extraction…")
        segments = self._grid_editor.current_segments()
        self._start_extraction_worker(pdf_path, profile, segments)

    def _on_cancel_extract(self) -> None:
        if not self._is_extracting() or self._extraction_worker is None:
            return
        self._cancel_extract_btn.setEnabled(False)
        self._set_status("Cancelling extraction after the current page…")
        self._extraction_worker.cancel()

    def _on_extraction_progress(self, page_index: int, page_count: int, pairs_extracted: int) -> None:
        completed = page_index + 1
        pct = int((completed / page_count) * 100) if page_count else 0
        self._progress_bar.setValue(max(0, min(100, pct)))
        self._set_status(
            f"Extracting page {completed}/{page_count} • {pairs_extracted} pairs found"
        )

    def _on_extraction_finished(self, pairs: object, was_cancelled: bool) -> None:
        extracted_pairs = list(pairs) if isinstance(pairs, list) else []
        self._preview_panel.load(extracted_pairs)
        self._preview_panel.setVisible(bool(extracted_pairs))
        if extracted_pairs:
            self._splitter.setSizes([900, 520])

        self._set_extraction_running(False)
        if was_cancelled:
            msg = f"Extraction cancelled: {len(extracted_pairs)} pairs found."
            self._set_status(msg)
            Toast.show_in(self.window(), msg, success=False)
        else:
            msg = f"Extraction complete: {len(extracted_pairs)} pairs found."
            self._set_status(msg)
            Toast.show_in(self.window(), msg, success=True)

    def _on_extraction_failed(self, error: str) -> None:
        self._set_extraction_running(False)
        self._set_status("Extraction failed.")
        detail = error[:120] + "…" if len(error) > 120 else error
        Toast.show_in(self.window(), f"Extraction failed: {detail}", success=False)

    def _on_extraction_thread_finished(self) -> None:
        self._extraction_thread = None
        self._extraction_worker = None

    def _set_status(self, text: str) -> None:
        """Update the compact status area without letting long text stretch the toolbar."""
        self._status_label.setText(text)
        self._status_label.setToolTip(text)

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

    # ------------------------------------------------------------------
    # Extraction worker management
    # ------------------------------------------------------------------

    def _start_extraction_worker(self, pdf_path: str, profile: Grid, segments: list[GridSegment]) -> None:
        thread = QThread(self)
        worker = _ExtractionWorker(pdf_path, profile, segments)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_extraction_progress)
        worker.finished.connect(self._on_extraction_finished)
        worker.failed.connect(self._on_extraction_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_extraction_thread_finished)

        self._extraction_thread = thread
        self._extraction_worker = worker
        self._set_extraction_running(True)
        thread.start()

    def _set_extraction_running(self, running: bool) -> None:
        self._open_btn.setEnabled(not running)
        self._profile_button.setEnabled(not running)
        self._save_profile_btn.setEnabled(not running)
        self._extract_btn.setEnabled(not running)
        self._grid_editor.setEnabled(not running)

        self._cancel_extract_btn.setVisible(running)
        self._cancel_extract_btn.setEnabled(running)
        self._progress_bar.setVisible(running)
        if running:
            self._progress_bar.setValue(0)
        else:
            self._progress_bar.setValue(0)
            self._progress_bar.setVisible(False)

    def _is_extracting(self) -> bool:
        return self._extraction_thread is not None and self._extraction_thread.isRunning()

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if self._is_extracting() and self._extraction_worker is not None:
            self._extraction_worker.cancel()
            if self._extraction_thread is not None:
                self._extraction_thread.quit()
                self._extraction_thread.wait(1500)
        super().closeEvent(event)


