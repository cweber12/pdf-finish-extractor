import json
from pathlib import Path

from src.extraction.grid import (
    CellGroup,
    FieldDefinition,
    Grid,
    GridExtractionProfile,
    GridSegment,
    OmitRegion,
)
from src.extraction.pattern import (
    ImageSampleDefinition,
    ImageTextPattern,
    ImageTextPatternProfile,
    PatternDetectionOptions,
    RectPx,
    RelativeRect,
    TextSectionDefinition,
)
from src.profiles.repository import ProfileRepository, load_profile_from_dict, safe_profile_name


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
        fields=[FieldDefinition("swatch", "image", 1), FieldDefinition("sku", "text", 1)],
        omitted_pages=[2],
        omit_regions=[OmitRegion(page_index=1, rect=(10, 20, 40, 60))],
    )
    segments = [
        GridSegment(
            start_page=0,
            horizontal_lines=[100, 250],
            vertical_lines=[80],
            groups=[CellGroup(field_cells={"swatch": [(0, 0)], "sku": [(1, 0)]})],
        ),
        GridSegment(
            start_page=3,
            horizontal_lines=[120],
            vertical_lines=[90],
            groups=[],
        ),
    ]
    profile = GridExtractionProfile(grid=grid, segments=segments)

    saved_name = repo.save("  Catalog/Profile  ", profile)
    loaded = repo.load(saved_name)

    assert saved_name == "Catalog-Profile"
    assert loaded is not None
    assert loaded.to_dict() == profile.to_dict()
    assert len(loaded.segments) == 2
    assert loaded.segments[0].start_page == 0
    assert loaded.segments[1].start_page == 3


def test_load_migrates_old_grid_only_format(tmp_path: Path) -> None:
    """Old-format profiles (no profile_type) are migrated to GridExtractionProfile."""
    import json

    old_data = {
        "horizontal_lines": [100, 200],
        "vertical_lines": [50],
        "fields": [{"name": "sku", "type": "text", "click_count": 1}],
        "groups": [],
        "omitted_pages": [],
        "omit_regions": [],
    }
    (tmp_path / "legacy.json").write_text(json.dumps(old_data), encoding="utf-8")
    repo = ProfileRepository(tmp_path)

    loaded = repo.load("legacy")

    assert loaded is not None
    assert len(loaded.segments) == 1
    assert loaded.segments[0].start_page == 0
    assert loaded.segments[0].horizontal_lines == [100, 200]
    assert loaded.segments[0].vertical_lines == [50]


def test_list_profiles_is_sorted(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    profile = GridExtractionProfile(
        grid=Grid(fields=[FieldDefinition("id", "text", 1)]),
        segments=[GridSegment(start_page=0)],
    )
    repo.save("zeta", profile)
    repo.save("alpha", profile)
    repo.save("beta", profile)

    assert repo.list_profiles() == ["alpha", "beta", "zeta"]


def test_load_missing_profile_returns_none(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)

    assert repo.load("does-not-exist") is None


def test_delete_returns_true_only_when_profile_exists(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    profile = GridExtractionProfile(
        grid=Grid(fields=[FieldDefinition("id", "text", 1)]),
        segments=[GridSegment(start_page=0)],
    )
    repo.save("to-delete", profile)

    assert repo.delete("to-delete") is True
    assert repo.delete("to-delete") is False


def _make_pattern_profile() -> ImageTextPatternProfile:
    sample = ImageSampleDefinition(
        rect_px=RectPx(x0=10, y0=20, x1=110, y1=120),
        width_px=100,
        height_px=100,
        aspect_ratio=1.0,
    )
    text_section = TextSectionDefinition(
        name="finish_name",
        index=0,
        relative_rect=RelativeRect(x0=0.0, y0=1.05, x1=1.0, y1=1.30),
    )
    pattern = ImageTextPattern(
        sample=sample,
        text_side="below",
        segmentation="rows",
        text_sections=[text_section],
    )
    return ImageTextPatternProfile(
        pattern=pattern,
        detection_options=PatternDetectionOptions(),
    )


def test_load_profile_from_dict_routes_manual_grid() -> None:
    grid = Grid(fields=[FieldDefinition("sku", "text", 1)])
    profile = GridExtractionProfile(grid=grid, segments=[GridSegment(start_page=0)])
    loaded = load_profile_from_dict(profile.to_dict())
    assert isinstance(loaded, GridExtractionProfile)


def test_load_profile_from_dict_routes_image_text_pattern() -> None:
    profile = _make_pattern_profile()
    loaded = load_profile_from_dict(profile.to_dict())
    assert isinstance(loaded, ImageTextPatternProfile)


def test_load_profile_from_dict_returns_none_for_unknown_type() -> None:
    data = {"profile_type": "future_unknown_mode", "version": 99}
    assert load_profile_from_dict(data) is None


def test_save_and_load_image_text_pattern_profile(tmp_path: Path) -> None:
    repo = ProfileRepository(tmp_path)
    profile = _make_pattern_profile()

    saved_name = repo.save("pattern-test", profile)
    loaded = repo.load(saved_name)

    assert isinstance(loaded, ImageTextPatternProfile)
    assert loaded.to_dict() == profile.to_dict()
    assert loaded.pattern.text_side == "below"
    assert len(loaded.pattern.text_sections) == 1
    assert loaded.pattern.text_sections[0].name == "finish_name"
