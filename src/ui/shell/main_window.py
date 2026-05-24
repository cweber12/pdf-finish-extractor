from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QCloseEvent, QColor, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme
from src.ui.feedback.extraction_feedback import (
    coerce_extracted_groups,
    extraction_completion_message,
    extraction_failure_toast,
    extraction_progress_status,
    extraction_progress_value,
    toolbar_state_for_running,
)
from src.ui.runtime.extraction_session import ExtractionSession
from src.ui.grid_editor import GlowIconButton, GridEditor
from src.ui.shell.main_window_intents import (
    busy_guard_message,
    extract_preflight_error,
    named_event_message,
    save_profile_preflight_error,
)
from src.ui.profiles.profile_menu import apply_selected_layout_label, populate_profile_menu
from src.ui.panels.preview_panel import PreviewPanel
from src.ui.profiles.profile_manager import ProfileManager
from src.ui.feedback.toast import Toast

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Finish Extractor")
        self.resize(1280, 900)

        self._profile_manager = ProfileManager()
        self._selected_profile_name: str | None = None
        self._extraction_session = ExtractionSession(self)
        self._extraction_session.progress.connect(self._on_extraction_progress)
        self._extraction_session.finished.connect(self._on_extraction_finished)
        self._extraction_session.failed.connect(self._on_extraction_failed)
        self._extraction_session.running_changed.connect(self._set_extraction_running)
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

        # File action — text+icon button so the entry point reads clearly.
        self._open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
        self._open_btn.setObjectName("openPdfButton")
        self._open_btn.setIconSize(QSize(16, 16))
        self._open_btn.setToolTip("Open a PDF and start defining extraction boundaries.")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._on_open_pdf)
        layout.addWidget(self._open_btn)

        layout.addSpacing(10)

        # Grid Layouts cell — dropdown fills the entire cell, flush with the bar.
        layouts_cell = QWidget()
        layouts_cell.setObjectName("layoutsCell")
        cell_layout = QHBoxLayout(layouts_cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(0)

        self._profile_button = QToolButton()
        self._profile_button.setObjectName("layoutsDropdown")
        self._profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._profile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._profile_button.setIcon(QIcon(theme.icon_path("layers.svg")))
        self._profile_button.setIconSize(QSize(16, 16))
        self._profile_button.setText("Grid Layouts")
        self._profile_button.setToolTip(
            "Load a saved grid layout or save the current one."
        )
        self._profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._profile_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._profile_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._profile_menu = QMenu(self._profile_button)
        self._profile_button.setMenu(self._profile_menu)
        cell_layout.addWidget(self._profile_button)

        layouts_cell.setMinimumWidth(280)
        layout.addWidget(layouts_cell, alignment=Qt.AlignmentFlag.AlignBottom)

        self._refresh_profiles()

        layout.addSpacing(10)

        # Extract action — primary text+icon button with the new extract glyph.
        self._extract_btn = QPushButton(QIcon(theme.icon_path("extract.svg")), "  Extract")
        self._extract_btn.setObjectName("extractButton")
        self._extract_btn.setIconSize(QSize(16, 16))
        self._extract_btn.setToolTip("Run extraction using the current grid groups.")
        self._extract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        """Logo + title cluster on the left of the action bar."""
        cluster = QWidget()
        cluster.setObjectName("brandCluster")
        cluster_layout = QHBoxLayout(cluster)
        cluster_layout.setContentsMargins(0, 0, 8, 0)
        cluster_layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("brandMark")
        logo.setFixedSize(36, 36)
        logo.setPixmap(QIcon(theme.icon_path("logo-mark.svg")).pixmap(36, 36))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cluster_layout.addWidget(logo)

        app_title = QLabel("PDF Finish Extractor")
        app_title.setObjectName("appTitle")
        app_title.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        cluster_layout.addWidget(app_title)
        return cluster

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_open_pdf(self) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), busy_guard_message("open_pdf"), success=False)
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
            Toast.show_in(self.window(), busy_guard_message("change_profile"), success=False)
            return

        profile = self._profile_manager.load(name)
        if profile:
            self._grid_editor.apply_profile(profile)
            self._selected_profile_name = name
            self._set_selected_layout_label(name)
            msg = named_event_message("Profile applied", name)
            self._set_status(msg)
            Toast.show_in(self.window(), msg, success=True)

    def _on_save_profile(self) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), busy_guard_message("save_profile"), success=False)
            return

        profile = self._grid_editor.current_profile()
        profile_error = save_profile_preflight_error(profile_exists=(profile is not None))
        if profile_error:
            Toast.show_in(self.window(), profile_error, success=False)
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
        msg = named_event_message("Profile saved", saved_name)
        self._set_status(msg)
        Toast.show_in(self.window(), msg, success=True)

    def _set_selected_layout_label(self, name: str | None) -> None:
        apply_selected_layout_label(self._profile_button, name)

    def _on_extract(self) -> None:
        if self._is_extracting():
            return

        profile = self._grid_editor.current_profile()
        pdf_path = self._grid_editor.pdf_path
        preflight_error = extract_preflight_error(
            pdf_path=pdf_path,
            profile_exists=bool(profile),
        )
        if preflight_error:
            Toast.show_in(self.window(), preflight_error, success=False)
            return

        self._preview_panel.setVisible(False)
        self._set_status("Preparing extraction…")
        segments = self._grid_editor.current_segments()
        self._extraction_session.start(pdf_path, profile, segments)

    def _on_cancel_extract(self) -> None:
        if not self._is_extracting():
            return
        self._cancel_extract_btn.setEnabled(False)
        self._set_status("Cancelling extraction after the current page…")
        self._extraction_session.cancel()

    def _on_extraction_progress(self, page_index: int, page_count: int, groups_extracted: int) -> None:
        self._progress_bar.setValue(extraction_progress_value(page_index, page_count))
        self._set_status(extraction_progress_status(page_index, page_count, groups_extracted))

    def _on_extraction_finished(self, groups: object, was_cancelled: bool) -> None:
        extracted_groups = coerce_extracted_groups(groups)
        self._preview_panel.load(extracted_groups)
        self._preview_panel.setVisible(bool(extracted_groups))
        if extracted_groups:
            self._splitter.setSizes([900, 520])

        msg, success = extraction_completion_message(len(extracted_groups), was_cancelled)
        self._set_status(msg)
        Toast.show_in(self.window(), msg, success=success)

    def _on_extraction_failed(self, error: str) -> None:
        self._set_status("Extraction failed.")
        Toast.show_in(self.window(), extraction_failure_toast(error), success=False)

    def _set_status(self, text: str) -> None:
        """Update the compact status area without letting long text stretch the toolbar."""
        self._status_label.setText(text)
        self._status_label.setToolTip(text)

    def _refresh_profiles(self) -> None:
        if not hasattr(self, "_profile_menu"):
            return

        populate_profile_menu(
            self._profile_menu,
            profile_names=self._profile_manager.list_profiles(),
            selected_profile_name=self._selected_profile_name,
            on_apply=self._on_profile_row_apply,
            on_delete=self._on_profile_row_delete,
            on_save=self._on_save_profile,
            owner=self,
            save_icon=QIcon(theme.icon_path("save.svg")),
        )

    def _on_profile_row_apply(self, name: str) -> None:
        self._profile_menu.close()
        self._on_profile_selected(name)

    def _on_profile_row_delete(self, name: str) -> None:
        self._profile_menu.close()
        self._on_delete_profile(name)

    def _on_delete_profile(self, name: str) -> None:
        if self._is_extracting():
            Toast.show_in(self.window(), busy_guard_message("delete_layout"), success=False)
            return

        confirm = QMessageBox(self)
        confirm.setWindowTitle("Delete layout")
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setText(f"Delete the saved layout '{name}'?")
        confirm.setInformativeText("This cannot be undone.")
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        if not self._profile_manager.delete(name):
            Toast.show_in(self.window(), f"Layout not found: {name}", success=False)
            return

        if self._selected_profile_name == name:
            self._selected_profile_name = None
            self._set_selected_layout_label(None)

        self._refresh_profiles()
        msg = named_event_message("Layout deleted", name)
        self._set_status(msg)
        Toast.show_in(self.window(), msg, success=True)

    def _set_extraction_running(self, running: bool) -> None:
        state = toolbar_state_for_running(running)
        self._open_btn.setEnabled(state.open_enabled)
        self._profile_button.setEnabled(state.profile_enabled)
        self._extract_btn.setEnabled(state.extract_enabled)
        self._grid_editor.setEnabled(state.grid_enabled)

        self._cancel_extract_btn.setVisible(state.cancel_visible)
        self._cancel_extract_btn.setEnabled(state.cancel_enabled)
        self._progress_bar.setValue(state.progress_value)
        self._progress_bar.setVisible(state.progress_visible)

    def _is_extracting(self) -> bool:
        return self._extraction_session.is_running()

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if self._is_extracting():
            self._extraction_session.shutdown(1500)
        super().closeEvent(event)


