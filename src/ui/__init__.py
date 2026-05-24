__all__ = ["MainWindow", "PDFViewer", "GridEditor", "PreviewPanel", "ProfileManager", "Toast"]


def __getattr__(name: str) -> object:
    if name == "MainWindow":
        from src.ui.shell.main_window import MainWindow

        return MainWindow
    if name == "PDFViewer":
        from src.ui.editor.pdf_viewer import PDFViewer

        return PDFViewer
    if name == "GridEditor":
        from src.ui.editor.grid_editor import GridEditor

        return GridEditor
    if name == "PreviewPanel":
        from src.ui.panels.preview_panel import PreviewPanel

        return PreviewPanel
    if name == "ProfileManager":
        from src.ui.profiles.profile_manager import ProfileManager

        return ProfileManager
    if name == "Toast":
        from src.ui.feedback.toast import Toast

        return Toast
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
