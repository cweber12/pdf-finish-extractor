from __future__ import annotations

_MODE_HINTS = {
    "idle": "Drag existing handles to move lines. Right-click a line to remove it.",
    "add_h": "Click-drag across the PDF to place a horizontal row boundary.",
    "add_v": "Click-drag across the PDF to place a vertical column boundary.",
    "grouping": "Click cells in field order until the group is complete.",
    "omit": "Click-drag a section on this page to ignore during extraction. Right-click an ignored section to remove it.",
}


def resolved_mode(requested_mode: str, *, is_checked: bool) -> str:
    return requested_mode if is_checked else "idle"


def mode_hint(mode: str) -> str:
    return _MODE_HINTS.get(mode, _MODE_HINTS["idle"])


def mode_uses_crosshair(mode: str) -> bool:
    return mode in ("add_h", "add_v", "omit")

