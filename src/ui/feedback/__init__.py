"""Feedback-related UI helpers."""

__all__ = [
    "Toast",
    "coerce_extracted_groups",
    "extraction_completion_message",
    "extraction_failure_toast",
    "extraction_progress_status",
    "extraction_progress_value",
    "toolbar_state_for_running",
]


def __getattr__(name: str) -> object:
    if name == "Toast":
        from src.ui.feedback.toast import Toast

        return Toast
    if name == "coerce_extracted_groups":
        from src.ui.feedback.extraction_feedback import coerce_extracted_groups

        return coerce_extracted_groups
    if name == "extraction_completion_message":
        from src.ui.feedback.extraction_feedback import extraction_completion_message

        return extraction_completion_message
    if name == "extraction_failure_toast":
        from src.ui.feedback.extraction_feedback import extraction_failure_toast

        return extraction_failure_toast
    if name == "extraction_progress_status":
        from src.ui.feedback.extraction_feedback import extraction_progress_status

        return extraction_progress_status
    if name == "extraction_progress_value":
        from src.ui.feedback.extraction_feedback import extraction_progress_value

        return extraction_progress_value
    if name == "toolbar_state_for_running":
        from src.ui.feedback.extraction_feedback import toolbar_state_for_running

        return toolbar_state_for_running
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
