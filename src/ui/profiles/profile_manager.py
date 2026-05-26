from __future__ import annotations

from pathlib import Path

from src.profiles.repository import ExtractionProfile, ProfileRepository


class ProfileManager:
    """UI-facing adapter over profile persistence repository."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._repository = ProfileRepository(profiles_dir)

    def list_profiles(self) -> list[str]:
        return self._repository.list_profiles()

    def save(self, name: str, profile: ExtractionProfile | None) -> str:
        """Save *profile* as *name* and return the normalized saved name."""
        if profile is None:
            raise ValueError("Create at least one grid line before saving a profile.")
        return self._repository.save(name, profile)

    def load(self, name: str) -> ExtractionProfile | None:
        return self._repository.load(name)

    def delete(self, name: str) -> bool:
        """Delete the saved profile named *name*. Returns True if a file was removed."""
        return self._repository.delete(name)
