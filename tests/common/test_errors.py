from __future__ import annotations

from src.common.errors import AppError, to_user_message


def test_to_user_message_prefers_typed_error_user_message() -> None:
    error = AppError("Friendly message", detail="internal detail")
    assert to_user_message(error, fallback="fallback") == "Friendly message"


def test_to_user_message_uses_fallback_for_blank_exception_message() -> None:
    assert to_user_message(Exception("   "), fallback="Fallback message") == "Fallback message"


def test_to_user_message_truncates_long_messages() -> None:
    text = "x" * 130
    assert to_user_message(Exception(text), fallback="fallback", max_len=10) == ("x" * 10) + "…"
