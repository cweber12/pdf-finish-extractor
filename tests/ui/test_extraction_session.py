from __future__ import annotations

from src.ui.extraction_session import ExtractionSession


class _FakeWorker:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1


class _FakeThread:
    def __init__(self, *, running: bool) -> None:
        self.running = running
        self.quit_calls = 0
        self.wait_calls: list[int] = []

    def isRunning(self) -> bool:  # noqa: N802 - match Qt naming
        return self.running

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)


def test_session_cancel_forwards_to_worker() -> None:
    session = ExtractionSession()
    worker = _FakeWorker()
    session._worker = worker  # noqa: SLF001 - targeted seam contract test

    session.cancel()

    assert worker.cancel_calls == 1


def test_session_is_running_reflects_thread_state() -> None:
    session = ExtractionSession()
    session._thread = _FakeThread(running=True)  # noqa: SLF001 - targeted seam contract test
    assert session.is_running() is True

    session._thread = _FakeThread(running=False)  # noqa: SLF001 - targeted seam contract test
    assert session.is_running() is False


def test_session_shutdown_cancels_worker_and_waits_for_thread() -> None:
    session = ExtractionSession()
    worker = _FakeWorker()
    thread = _FakeThread(running=True)
    session._worker = worker  # noqa: SLF001 - targeted seam contract test
    session._thread = thread  # noqa: SLF001 - targeted seam contract test

    session.shutdown(987)

    assert worker.cancel_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [987]


def test_on_thread_finished_clears_refs_and_emits_running_false() -> None:
    session = ExtractionSession()
    session._worker = _FakeWorker()  # noqa: SLF001 - targeted seam contract test
    session._thread = _FakeThread(running=False)  # noqa: SLF001 - targeted seam contract test
    running_events: list[bool] = []
    session.running_changed.connect(running_events.append)

    session._on_thread_finished()  # noqa: SLF001 - targeted seam contract test

    assert session._worker is None  # noqa: SLF001 - targeted seam contract test
    assert session._thread is None  # noqa: SLF001 - targeted seam contract test
    assert running_events == [False]
