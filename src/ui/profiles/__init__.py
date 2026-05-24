"""Profile-related UI package."""

__all__ = ["ProfileManager", "apply_selected_layout_label", "populate_profile_menu"]


def __getattr__(name: str) -> object:
    if name == "ProfileManager":
        from src.ui.profiles.profile_manager import ProfileManager

        return ProfileManager
    if name == "apply_selected_layout_label":
        from src.ui.profiles.profile_menu import apply_selected_layout_label

        return apply_selected_layout_label
    if name == "populate_profile_menu":
        from src.ui.profiles.profile_menu import populate_profile_menu

        return populate_profile_menu
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
