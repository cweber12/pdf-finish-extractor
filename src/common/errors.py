from __future__ import annotations


class AppError(Exception):
    """Base application error with a user-safe message."""

    def __init__(self, user_message: str, *, detail: str = "") -> None:
        super().__init__(detail or user_message)
        self.user_message = user_message.strip() or "Operation failed."
        self.detail = detail.strip()


class ExtractionError(AppError):
    """Raised when extraction cannot complete safely."""


class ExportError(AppError):
    """Raised when export output cannot be produced."""


class UploadError(AppError):
    """Raised when upload workflow fails."""


class ProfileError(AppError):
    """Raised when profile operations fail."""


def to_user_message(exc: Exception, *, fallback: str, max_len: int = 120) -> str:
    """Return a safe message suitable for UI display."""
    if isinstance(exc, AppError):
        message = exc.user_message
    else:
        message = str(exc).strip() or fallback.strip()

    if len(message) > max_len:
        return message[:max_len].rstrip() + "…"
    return message
