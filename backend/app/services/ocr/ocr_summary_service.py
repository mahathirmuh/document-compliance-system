"""Deterministic OCR confidence, count, warning, and hash summaries."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models.ocr_page_result import OCRPageStatus
from app.schemas.ocr_internal import OCRPageResult


@dataclass(frozen=True, slots=True)
class OCRRunSummaryData:
    page_count_requested: int
    page_count_processed: int
    page_count_failed: int
    total_blocks: int
    total_characters: int
    average_confidence: float | None
    minimum_confidence: float | None
    maximum_confidence: float | None
    content_hash: str
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "pageCountRequested": self.page_count_requested,
            "pageCountProcessed": self.page_count_processed,
            "pageCountFailed": self.page_count_failed,
            "totalBlocks": self.total_blocks,
            "totalCharacters": self.total_characters,
            "averageConfidence": self.average_confidence,
            "minimumConfidence": self.minimum_confidence,
            "maximumConfidence": self.maximum_confidence,
            "contentHash": self.content_hash,
            "warnings": list(self.warnings),
        }


class OCRSummaryService:
    """Calculate summaries from typed page results, not provider objects."""

    def summarize(
        self,
        pages: list[OCRPageResult],
        *,
        requested_page_count: int | None = None,
    ) -> OCRRunSummaryData:
        confidences = [block.confidence for page in pages for block in page.blocks]
        processed = sum(page.status is not OCRPageStatus.FAILED for page in pages)
        failed = sum(page.status is OCRPageStatus.FAILED for page in pages)
        text_by_page = "\n".join(
            f"[PAGE {page.page_number}]\n{page.normalised_text}"
            for page in sorted(pages, key=lambda item: item.page_number)
        )
        return OCRRunSummaryData(
            page_count_requested=(
                requested_page_count if requested_page_count is not None else len(pages)
            ),
            page_count_processed=processed,
            page_count_failed=failed,
            total_blocks=sum(len(page.blocks) for page in pages),
            total_characters=sum(
                len(block.normalised_text) for page in pages for block in page.blocks
            ),
            average_confidence=(
                sum(confidences) / len(confidences) if confidences else None
            ),
            minimum_confidence=min(confidences) if confidences else None,
            maximum_confidence=max(confidences) if confidences else None,
            content_hash=hashlib.sha256(text_by_page.encode("utf-8")).hexdigest(),
            warnings=tuple(
                dict.fromkeys(
                    warning for page in pages for warning in page.warning_codes
                )
            ),
        )
