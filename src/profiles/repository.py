from __future__ import annotations

import json
import re
from pathlib import Path

from src.extraction.grid import Grid


def default_profiles_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "profiles"


def safe_profile_name(name: str) -> str:
    """Return a filesystem-safe profile name while preserving readability."""
    cleaned = re.sub(r"[^A-Za-z0-9_. -]+", "-", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    if not cleaned:
        raise ValueError("Profile name cannot be empty.")
    return cleaned


class ProfileRepository:
    """Filesystem-backed repository for profile JSON documents."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._profiles_dir = profiles_dir or default_profiles_dir()
        self._profiles_dir.mkdir(exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(path.stem for path in self._profiles_dir.glob("*.json"))

    def save(self, name: str, grid: Grid) -> str:
        saved_name = safe_profile_name(name)
        path = self._profiles_dir / f"{saved_name}.json"
        path.write_text(json.dumps(grid.to_dict(), indent=2), encoding="utf-8")
        return saved_name

    def load(self, name: str) -> Grid | None:
        safe_name = safe_profile_name(name)
        path = self._profiles_dir / f"{safe_name}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Grid.from_dict(data)

    def delete(self, name: str) -> bool:
        safe_name = safe_profile_name(name)
        path = self._profiles_dir / f"{safe_name}.json"
        if not path.exists():
            return False
        path.unlink()
        return True
