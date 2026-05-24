"""UI panels package."""

__all__ = ["PreviewPanel"]


def __getattr__(name: str) -> object:
    if name == "PreviewPanel":
        from src.ui.panels.preview_panel import PreviewPanel

        return PreviewPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
