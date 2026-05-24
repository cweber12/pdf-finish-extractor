from pathlib import Path

from src.extraction.grid import CellGroup, FieldDefinition, Grid, OmitRegion
from src.profiles.repository import ProfileRepository, safe_profile_name


def test_safe_profile_name_normalizes_invalid_characters() -> None:
    assert safe_profile_name("  Maple/Oak* Finish  ") == "Maple-Oak- Finish"


def test_safe_profile_name_rejects_empty_names() -> None:
    try:
        safe_profile_name("  ...  ")
    except ValueError as exc:
        assert str(exc) == "Profile name cannot be empty."
    else:
        raise AssertionError("Expected ValueError for empty profile name")


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    grid = Grid(
        horizontal_lines=[100, 250],
        vertical_lines=[80],
        fields=[FieldDefinition("swatch", "image", 1), FieldDefinition("sku", "text", 1)],
        groups=[CellGroup(field_cells={"swatch": [(0, 0)], "sku": [(1, 0)]})],
        omitted_pages=[2],
        omit_regions=[OmitRegion(page_index=1, rect=(10, 20, 40, 60))],
    )

    saved_name = repo.save("  Catalog/Profile  ", grid)

    loaded = repo.load(saved_name)

    assert saved_name == "Catalog-Profile"
    assert loaded is not None
    assert loaded.to_dict() == grid.to_dict()


def test_list_profiles_is_sorted(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    grid = Grid(fields=[FieldDefinition("id", "text", 1)])
    repo.save("zeta", grid)
    repo.save("alpha", grid)
    repo.save("beta", grid)

    assert repo.list_profiles() == ["alpha", "beta", "zeta"]


def test_load_missing_profile_returns_none(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)

    assert repo.load("does-not-exist") is None


def test_delete_returns_true_only_when_profile_exists(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    grid = Grid(fields=[FieldDefinition("id", "text", 1)])
    repo.save("to-delete", grid)

    assert repo.delete("to-delete") is True
    assert repo.delete("to-delete") is False
