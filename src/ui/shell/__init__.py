"""Shell-level UI orchestration package."""

__all__ = [
    "MainWindow",
    "busy_guard_message",
    "extract_preflight_error",
    "named_event_message",
    "save_profile_preflight_error",
]


def __getattr__(name: str) -> object:
    if name == "MainWindow":
        from src.ui.shell.main_window import MainWindow

        return MainWindow
    if name == "busy_guard_message":
        from src.ui.shell.main_window_intents import busy_guard_message

        return busy_guard_message
    if name == "extract_preflight_error":
        from src.ui.shell.main_window_intents import extract_preflight_error

        return extract_preflight_error
    if name == "named_event_message":
        from src.ui.shell.main_window_intents import named_event_message

        return named_event_message
    if name == "save_profile_preflight_error":
        from src.ui.shell.main_window_intents import save_profile_preflight_error

        return save_profile_preflight_error
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
