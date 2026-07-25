"""Deduplicate multi-pass OCR and expose a provenance-safe merged view."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.schemas.ocr_internal import OCRBlockData, OCRMergedBlock


class OCRMergeService:
    """Merge without overwriting native extraction content."""

    def deduplicate_provider_blocks(
        self,
        blocks: Iterable[OCRBlockData],
    ) -> list[OCRBlockData]:
        retained: list[OCRBlockData] = []
        for block in sorted(
            blocks,
            key=lambda item: (
                item.bbox.y,
                item.bbox.x,
                -item.confidence,
            ),
        ):
            duplicate_index = next(
                (
                    index
                    for index, candidate in enumerate(retained)
                    if self._is_duplicate(candidate, block)
                ),
                None,
            )
            if duplicate_index is None:
                retained.append(block)
            elif block.confidence > retained[duplicate_index].confidence:
                retained[duplicate_index] = block
        return retained

    def merge_native_and_ocr(
        self,
        native_blocks: Iterable[Mapping[str, Any]],
        ocr_blocks: Iterable[Mapping[str, Any]],
        *,
        selectable_text_minimum: int = 50,
    ) -> list[OCRMergedBlock]:
        """Build a read-only merged view, preferring sufficient native text."""
        native = list(native_blocks)
        ocr = list(ocr_blocks)
        native_characters: dict[int, int] = {}
        native_texts: dict[int, set[str]] = {}
        for block in native:
            page = int(block["page_number"])
            normalized = str(
                block.get("normalised_text") or block.get("text") or ""
            ).strip()
            native_characters[page] = native_characters.get(page, 0) + len(
                normalized
            )
            if normalized:
                native_texts.setdefault(page, set()).add(
                    normalized.casefold()
                )

        merged: list[OCRMergedBlock] = []
        for block in native:
            page = int(block["page_number"])
            merged.append(
                OCRMergedBlock(
                    source="NATIVE",
                    source_id=str(block["id"]),
                    page_number=page,
                    block_order=int(block.get("block_order", 0)),
                    text=str(block.get("text") or ""),
                    normalised_text=str(
                        block.get("normalised_text") or block.get("text") or ""
                    ),
                    confidence=None,
                    provenance={
                        "source": "EXTRACTION",
                        "extractionRunId": self._optional_string(
                            block.get("extraction_run_id")
                        ),
                        "extractedBlockId": str(block["id"]),
                        "containerId": self._optional_string(
                            block.get("container_id")
                        ),
                        "sourceReference": block.get("source_reference"),
                    },
                )
            )
        retained_ocr_texts: dict[int, set[str]] = {}
        for block in ocr:
            page = int(block["page_number"])
            if native_characters.get(page, 0) >= selectable_text_minimum:
                continue
            normalized = str(
                block.get("normalised_text") or block.get("text") or ""
            ).strip()
            normalized_key = normalized.casefold()
            if normalized_key and (
                normalized_key in native_texts.get(page, set())
                or normalized_key
                in retained_ocr_texts.setdefault(page, set())
            ):
                continue
            if normalized_key:
                retained_ocr_texts.setdefault(page, set()).add(
                    normalized_key
                )
            merged.append(
                OCRMergedBlock(
                    source="OCR",
                    source_id=str(block["id"]),
                    page_number=page,
                    block_order=int(block.get("block_order", 0)),
                    text=str(block.get("text") or ""),
                    normalised_text=str(
                        normalized
                    ),
                    confidence=float(block["confidence"]),
                    provenance={
                        "source": "OCR",
                        "ocrRunId": str(block["ocr_run_id"]),
                        "ocrPageResultId": str(block["ocr_page_result_id"]),
                        "ocrBlockId": str(block["id"]),
                        "pageNumber": page,
                        "providerModel": block.get("provider_model"),
                        "recognitionProfile": block.get("recognition_profile"),
                    },
                )
            )
        return sorted(
            merged,
            key=lambda item: (
                item.page_number,
                item.block_order,
                item.source,
                item.source_id,
            ),
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None

    @classmethod
    def _is_duplicate(
        cls,
        left: OCRBlockData,
        right: OCRBlockData,
    ) -> bool:
        left_text = left.normalised_text.casefold()
        right_text = right.normalised_text.casefold()
        same_text = left_text == right_text
        near_text = min(len(left_text), len(right_text)) >= 4 and (
            left_text in right_text or right_text in left_text
        )
        overlap = cls._intersection_over_union(left, right)
        comparable_length = (
            min(len(left_text), len(right_text))
            / max(1, max(len(left_text), len(right_text)))
            >= 0.6
        )
        return ((same_text or near_text) and overlap >= 0.5) or (
            comparable_length and overlap >= 0.85
        )

    @staticmethod
    def _intersection_over_union(
        left: OCRBlockData,
        right: OCRBlockData,
    ) -> float:
        left_x2 = left.bbox.x + left.bbox.width
        left_y2 = left.bbox.y + left.bbox.height
        right_x2 = right.bbox.x + right.bbox.width
        right_y2 = right.bbox.y + right.bbox.height
        intersection_width = max(
            0.0,
            min(left_x2, right_x2) - max(left.bbox.x, right.bbox.x),
        )
        intersection_height = max(
            0.0,
            min(left_y2, right_y2) - max(left.bbox.y, right.bbox.y),
        )
        intersection = intersection_width * intersection_height
        union = (
            left.bbox.width * left.bbox.height
            + right.bbox.width * right.bbox.height
            - intersection
        )
        return intersection / union if union > 0 else 0.0
