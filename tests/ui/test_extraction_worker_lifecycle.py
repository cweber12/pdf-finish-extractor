from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pytest import MonkeyPatch

from src.extraction.extractor import ExtractionProgress
from src.extraction.grid import Grid, GridSegment
from src.ui.runtime.extraction_session import _ExtractionWorker


def test_worker_emits_progress_and_finished(monkeypatch: MonkeyPatch) -> None:
    class FakeExtractor:
        def __init__(
            self,
            pdf_path: str,
            profile: Grid,
            *,
            segments: list[GridSegment] | None = None,
        ) -> None:
            self.pdf_path = pdf_path
            self.profile = profile
            self.segments = segments

        def extract_all_pages(
            self,
            *,
            progress_callback: Callable[[ExtractionProgress], None],
            cancel_check: Callable[[], bool],
        ) -> list[Any]:
            assert cancel_check() is False
            progress_callback(ExtractionProgress(page_index=0, page_count=2, groups_extracted=2))
            progress_callback(ExtractionProgress(page_index=1, page_count=2, groups_extracted=4))
            return ["g1", "g2", "g3", "g4"]

    monkeypatch.setattr("src.ui.runtime.extraction_session.Extractor", FakeExtractor)

    worker = _ExtractionWorker("dummy.pdf", profile=Grid(), segments=[])
    progress_events: list[tuple[int, int, int]] = []
    finished_events: list[tuple[list[object], bool]] = []
    failed_events: list[str] = []

    worker.progress.connect(lambda i, c, g: progress_events.append((i, c, g)))
    worker.finished.connect(lambda groups, cancelled: finished_events.append((list(groups), cancelled)))
    worker.failed.connect(failed_events.append)

    worker.run()

    assert progress_events == [(0, 2, 2), (1, 2, 4)]
    assert finished_events == [(["g1", "g2", "g3", "g4"], False)]
    assert failed_events == []


def test_worker_cancel_before_run_marks_finished_cancelled(monkeypatch: MonkeyPatch) -> None:
    class FakeExtractor:
        def __init__(
            self,
            pdf_path: str,
            profile: Grid,
            *,
            segments: list[GridSegment] | None = None,
        ) -> None:
            self.pdf_path = pdf_path

        def extract_all_pages(
            self,
            *,
            progress_callback: Callable[[ExtractionProgress], None],
            cancel_check: Callable[[], bool],
        ) -> list[Any]:
            assert cancel_check() is True
            return []

    monkeypatch.setattr("src.ui.runtime.extraction_session.Extractor", FakeExtractor)

    worker = _ExtractionWorker("dummy.pdf", profile=Grid(), segments=[])
    finished_events: list[tuple[list[object], bool]] = []

    worker.finished.connect(lambda groups, cancelled: finished_events.append((list(groups), cancelled)))
    worker.cancel()
    worker.run()

    assert finished_events == [([], True)]


def test_worker_emits_failed_on_extractor_error(monkeypatch: MonkeyPatch) -> None:
    class FakeExtractor:
        def __init__(
            self,
            pdf_path: str,
            profile: Grid,
            *,
            segments: list[GridSegment] | None = None,
        ) -> None:
            self.pdf_path = pdf_path

        def extract_all_pages(
            self,
            *,
            progress_callback: Callable[[ExtractionProgress], None],
            cancel_check: Callable[[], bool],
        ) -> list[Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr("src.ui.runtime.extraction_session.Extractor", FakeExtractor)

    worker = _ExtractionWorker("dummy.pdf", profile=Grid(), segments=[])
    failed_events: list[str] = []
    finished_events: list[tuple[list[object], bool]] = []

    worker.failed.connect(failed_events.append)
    worker.finished.connect(lambda groups, cancelled: finished_events.append((list(groups), cancelled)))

    worker.run()

    assert failed_events == ["boom"]
    assert finished_events == []


