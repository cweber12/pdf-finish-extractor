from __future__ import annotations

from pathlib import Path

from src.extraction.grid import Grid
from src.profiles.repository import ProfileRepository


class ProfileManager:
    """UI-facing adapter over profile persistence repository."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._repository = ProfileRepository(profiles_dir)

    def list_profiles(self) -> list[str]:
        return self._repository.list_profiles()

    def save(self, name: str, grid: Grid | None) -> str:
        """Save *grid* as *name* and return the normalized saved name."""
        if grid is None:
            raise ValueError("Create at least one grid line before saving a profile.")
        return self._repository.save(name, grid)

    def load(self, name: str) -> Grid | None:
        return self._repository.load(name)

    def delete(self, name: str) -> bool:
        """Delete the saved profile named *name*. Returns True if a file was removed."""
        return self._repository.delete(name)
