"""Project Code Extractor package."""

__version__ = "1.0.0"

from .extractor import (
    ExtractedFile,
    ExtractionResult,
    ProjectCodeExtractor,
    SkippedFile,
)

__all__ = [
    "ExtractedFile",
    "ExtractionResult",
    "ProjectCodeExtractor",
    "SkippedFile",
    "__version__",
]
