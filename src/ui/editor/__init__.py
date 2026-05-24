"""Grid editor and PDF viewer package."""

__all__ = ["GridEditor", "GlowIconButton", "PDFViewer"]


def __getattr__(name: str) -> object:
    if name == "GridEditor":
        from src.ui.editor.grid_editor import GridEditor

        return GridEditor
    if name == "GlowIconButton":
        from src.ui.editor.grid_editor_widgets import GlowIconButton

        return GlowIconButton
    if name == "PDFViewer":
        from src.ui.editor.pdf_viewer import PDFViewer

        return PDFViewer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

