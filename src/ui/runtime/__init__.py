"""Runtime/session UI helpers."""

__all__ = ["ExtractionSession", "_ExtractionWorker"]


def __getattr__(name: str) -> object:
    if name == "ExtractionSession":
        from src.ui.runtime.extraction_session import ExtractionSession

        return ExtractionSession
    if name == "_ExtractionWorker":
        from src.ui.runtime.extraction_session import _ExtractionWorker

        return _ExtractionWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
