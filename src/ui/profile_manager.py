from __future__ import annotations

import json
from pathlib import Path

from src.extraction.grid import Grid


_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


class ProfileManager:
    """Saves and loads named grid profiles from the ``profiles/`` directory."""

    def __init__(self) -> None:
        _PROFILES_DIR.mkdir(exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))

    def save(self, name: str, grid: Grid) -> None:
        path = _PROFILES_DIR / f"{name}.json"
        path.write_text(
            json.dumps(grid.to_dict(), indent=2), encoding="utf-8"
        )

    def load(self, name: str) -> Grid | None:
        path = _PROFILES_DIR / f"{name}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Grid.from_dict(data)
