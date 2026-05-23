from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from src.common.errors import to_user_message
from src.extraction.extractor import ExtractionProgress, Extractor
from src.extraction.grid import Grid, GridSegment


class _ExtractionWorker(QObject):
    """Runs PDF extraction off the Qt main thread."""

    progress = pyqtSignal(int, int, int)  # page_index, page_count, groups_extracted
    finished = pyqtSignal(object, bool)  # list[ExtractedGroup], was_cancelled
    failed = pyqtSignal(str)

    def __init__(self, pdf_path: str, profile: Grid, segments: list[GridSegment]) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._profile = profile
        self._segments = segments
        self._cancel_requested = False

    @pyqtSlot()
    def run(self) -> None:
        try:
            def on_progress(progress: ExtractionProgress) -> None:
                self.progress.emit(
                    progress.page_index,
                    progress.page_count,
                    progress.groups_extracted,
                )

            extractor = Extractor(self._pdf_path, self._profile, segments=self._segments or None)
            groups = extractor.extract_all_pages(
                progress_callback=on_progress,
                cancel_check=lambda: self._cancel_requested,
            )
            self.finished.emit(groups, self._cancel_requested)
        except Exception as exc:  # noqa: BLE001 - user-facing extraction failure
            self.failed.emit(
                to_user_message(
                    exc,
                    fallback="Could not extract data from this PDF.",
                    max_len=180,
                )
            )

    @pyqtSlot()
    def cancel(self) -> None:
        self._cancel_requested = True


class ExtractionSession(QObject):
    """Owns extraction worker/thread lifecycle behind a small UI seam."""

    progress = pyqtSignal(int, int, int)
    finished = pyqtSignal(object, bool)
    failed = pyqtSignal(str)
    running_changed = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _ExtractionWorker | None = None

    def start(self, pdf_path: str, profile: Grid, segments: list[GridSegment]) -> bool:
        if self.is_running():
            return False

        thread = QThread(self)
        worker = _ExtractionWorker(pdf_path, profile, segments)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self.progress)
        worker.finished.connect(self.finished)
        worker.failed.connect(self.failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._thread = thread
        self._worker = worker
        self.running_changed.emit(True)
        thread.start()
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def shutdown(self, wait_ms: int = 1500) -> None:
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(wait_ms)

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self.running_changed.emit(False)
