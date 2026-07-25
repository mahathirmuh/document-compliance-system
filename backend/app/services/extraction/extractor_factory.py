"""Central extension-to-extractor mapping for Phase 6."""

from collections.abc import Callable
from typing import ClassVar

from app.services.extraction.base_extractor import (
    BaseDocumentExtractor,
    UnsupportedExtractionFormatError,
)
from app.services.extraction.docx.docx_extractor import DOCXExtractor
from app.services.extraction.pdf.pdf_extractor import PDFExtractor
from app.services.extraction.xlsx.xlsx_extractor import XLSXExtractor

ExtractorBuilder = Callable[[], BaseDocumentExtractor]


class ExtractorFactory:
    """Construct the only three format extractors supported in Phase 6."""

    _extractors: ClassVar[dict[str, ExtractorBuilder]] = {
        "pdf": PDFExtractor,
        "docx": DOCXExtractor,
        "xlsx": XLSXExtractor,
    }

    @classmethod
    def get_extractor(cls, file_extension: str) -> BaseDocumentExtractor:
        normalized = BaseDocumentExtractor.normalize_extension(file_extension)
        builder = cls._extractors.get(normalized)
        if builder is None:
            raise UnsupportedExtractionFormatError(normalized)
        return builder()


def get_extractor(file_extension: str) -> BaseDocumentExtractor:
    """Convenience entry point for services that do not keep a factory."""
    return ExtractorFactory.get_extractor(file_extension)
