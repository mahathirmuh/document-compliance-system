"""Selectable-text PDF extractor backed by PyMuPDF."""

from pathlib import Path

import pymupdf
from pydantic import JsonValue

from app.schemas.extraction import ExtractedDocumentData
from app.services.extraction.base_extractor import (
    BaseDocumentExtractor,
    ExtractionError,
    ExtractionResourceLimitError,
)
from app.services.extraction.pdf.pdf_page_extractor import extract_pdf_page
from app.services.extraction.pdf.pdf_scan_detector import (
    PDFScanDetector,
    scanned_pages_warning,
)


class PDFExtractor(BaseDocumentExtractor):
    """Extract PDF metadata, pages, selectable text, blocks, and bounding boxes."""

    extractor_version = "1.0.0"

    def supports(self, extension: str) -> bool:
        return self.normalize_extension(extension) == "pdf"

    async def inspect(self, file_path: Path) -> dict[str, JsonValue]:
        file_size = self.validate_source_path(file_path)
        document = self._open_document(file_path)
        try:
            self._validate_document(document)
            return {
                "fileSize": file_size,
                "totalPages": document.page_count,
                "isEncrypted": bool(document.is_encrypted),
                "requiresPassword": bool(document.needs_pass),
                "metadata": _safe_pdf_metadata(document.metadata),
            }
        finally:
            document.close()

    async def extract(
        self,
        file_path: Path,
        context: dict[str, object],
    ) -> ExtractedDocumentData:
        extraction_context = self.resolve_context(context)
        file_size = self.validate_source_path(file_path, extraction_context)
        document = self._open_document(file_path)
        try:
            self._validate_document(document)
            if document.page_count > extraction_context.pdf_max_pages:
                raise ExtractionResourceLimitError(
                    "PDF_EXTRACTION_FAILED",
                    "The PDF exceeds the configured page limit.",
                    details={
                        "maximumPages": extraction_context.pdf_max_pages,
                        "actualPages": document.page_count,
                    },
                )

            containers = []
            scan_evidence = []
            warnings: list[str] = []
            total_images = 0
            for page_index in range(document.page_count):
                await self.checkpoint(
                    extraction_context,
                    10 + int((65 * page_index) / document.page_count),
                    f"Extracting page {page_index + 1} of {document.page_count}",
                )
                page_result = extract_pdf_page(
                    document.load_page(page_index),
                    page_index + 1,
                )
                containers.append(page_result.container)
                scan_evidence.append(page_result.scan_evidence)
                warnings.extend(page_result.warnings)
                total_images += page_result.scan_evidence.image_count

            if (
                not any(container.character_count for container in containers)
                and total_images == 0
            ):
                raise ExtractionError(
                    "PDF_EMPTY",
                    "The PDF does not contain extractable content.",
                )

            scan_detection = PDFScanDetector(
                minimum_characters_per_page=(
                    extraction_context.pdf_min_characters_per_page
                ),
                scanned_page_ratio_threshold=(
                    extraction_context.pdf_scanned_page_ratio_threshold
                ),
            ).detect(scan_evidence)
            if scan_detection.scanned_pages:
                warnings.append(
                    scanned_pages_warning(scan_detection.scanned_pages)
                )

            await self.checkpoint(
                extraction_context,
                75,
                "PDF extraction completed",
            )
            metadata: dict[str, JsonValue] = {
                "fileSize": file_size,
                "totalPages": document.page_count,
                "pdfMetadata": _safe_pdf_metadata(document.metadata),
                "scannedPages": list(scan_detection.scanned_pages),
                "scannedPageRatio": scan_detection.scanned_page_ratio,
                "totalImages": total_images,
            }
            return ExtractedDocumentData(
                extractor_type="PDF",
                extractor_version=self.extractor_version,
                status=scan_detection.status,
                metadata=metadata,
                containers=containers,
                warnings=_deduplicate(warnings),
                requires_ocr=scan_detection.requires_ocr,
                has_selectable_text=any(
                    container.character_count for container in containers
                ),
            )
        except ExtractionError:
            raise
        except (RuntimeError, ValueError, TypeError) as exc:
            raise ExtractionError(
                "PDF_EXTRACTION_FAILED",
                "The PDF content could not be extracted.",
            ) from exc
        finally:
            document.close()

    @staticmethod
    def _open_document(file_path: Path) -> pymupdf.Document:
        try:
            return pymupdf.open(file_path)
        except pymupdf.EmptyFileError as exc:
            raise ExtractionError(
                "PDF_EMPTY",
                "The PDF is empty.",
            ) from exc
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise ExtractionError(
                "PDF_CORRUPT",
                "The PDF is corrupt or is not a valid PDF document.",
            ) from exc

    @staticmethod
    def _validate_document(document: pymupdf.Document) -> None:
        if document.needs_pass:
            raise ExtractionError(
                "PDF_PASSWORD_REQUIRED",
                "This PDF is password-protected and cannot be extracted.",
            )
        if document.page_count <= 0:
            raise ExtractionError(
                "PDF_EMPTY",
                "The PDF does not contain any pages.",
            )


def _safe_pdf_metadata(metadata: object) -> dict[str, JsonValue]:
    if not isinstance(metadata, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in metadata.items()
        if value not in (None, "")
    }


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
