from src.extraction.grid import CellGroup, FieldDefinition, Grid

__all__ = ["Grid", "CellGroup", "FieldDefinition", "Extractor", "compress_image"]


def __getattr__(name: str) -> object:
    if name == "Extractor":
        from src.extraction.extractor import Extractor

        return Extractor
    if name == "compress_image":
        from src.extraction.image_processing import compress_image

        return compress_image
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
