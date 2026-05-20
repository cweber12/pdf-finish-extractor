from __future__ import annotations

import json
import re
from pathlib import Path

from src.extraction.grid import Grid

_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


def _safe_profile_name(name: str) -> str:
    """Return a filesystem-safe profile name while preserving readability."""
    cleaned = re.sub(r"[^A-Za-z0-9_. -]+", "-", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    if not cleaned:
        raise ValueError("Profile name cannot be empty.")
    return cleaned


class ProfileManager:
    """Saves and loads named grid profiles from the ``profiles/`` directory."""

    def __init__(self) -> None:
        _PROFILES_DIR.mkdir(exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))

    def save(self, name: str, grid: Grid | None) -> str:
        """Save *grid* as *name* and return the normalized saved name."""
        if grid is None:
            raise ValueError("Create at least one grid line before saving a profile.")

        saved_name = _safe_profile_name(name)
        path = _PROFILES_DIR / f"{saved_name}.json"
        path.write_text(json.dumps(grid.to_dict(), indent=2), encoding="utf-8")
        return saved_name

    def load(self, name: str) -> Grid | None:
        safe_name = _safe_profile_name(name)
        path = _PROFILES_DIR / f"{safe_name}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Grid.from_dict(data)
