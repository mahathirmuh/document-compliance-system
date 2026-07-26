"""Page-level PyMuPDF extraction and layout metadata normalization."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import pymupdf
from pydantic import JsonValue

from app.schemas.extraction import (
    ExtractedContainerData,
    ExtractedContainerType,
)
from app.services.extraction.pdf.pdf_block_normalizer import (
    normalize_bbox,
    normalize_pdf_block,
)
from app.services.extraction.pdf.pdf_scan_detector import PDFPageScanEvidence
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)


@dataclass(frozen=True, slots=True)
class ExtractedPDFPage:
    """One normalized page plus evidence used by scan detection."""

    container: ExtractedContainerData
    scan_evidence: PDFPageScanEvidence
    warnings: tuple[str, ...]


def _image_statistics(
    page: Any,
    *,
    page_area: float,
) -> tuple[int, float]:
    if page_area <= 0:
        return 0, 0.0
    largest_area = 0.0
    try:
        image_info = page.get_image_info()
    except (AttributeError, RuntimeError, ValueError):
        return 0, 0.0
    for item in image_info:
        if not isinstance(item, Mapping):
            continue
        x0, y0, x1, y1 = normalize_bbox(item.get("bbox"))
        largest_area = max(largest_area, (x1 - x0) * (y1 - y0))
    return len(image_info), min(1.0, largest_area / page_area)


def extract_pdf_page(page: Any, page_number: int) -> ExtractedPDFPage:
    """Extract selectable text blocks and finite page geometry."""
    text_dictionary = page.get_text(
        "dict",
        sort=True,
        flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES,
    )
    raw_blocks = text_dictionary.get("blocks", [])
    if not isinstance(raw_blocks, list):
        raw_blocks = []

    blocks = []
    text_block_order = 0
    text_source_number = 0
    horizontal_bands: list[tuple[float, float, float]] = []
    for source_number, raw_block in enumerate(raw_blocks, start=1):
        if not isinstance(raw_block, Mapping) or raw_block.get("type") != 0:
            continue
        text_source_number += 1
        text_block_order += 1
        normalized = normalize_pdf_block(
            raw_block,
            page_number=page_number,
            source_block_number=source_number,
            block_order=text_block_order,
        )
        if normalized is None:
            text_block_order -= 1
            continue
        blocks.append(normalized)
        bbox = normalized.location["bbox"]
        assert isinstance(bbox, list)
        horizontal_bands.append(
            (
                float(cast(Any, bbox[0])),
                float(cast(Any, bbox[1])),
                float(cast(Any, bbox[3])),
            )
        )

    raw_text = "\n".join(block.text for block in blocks)
    normalised_text = normalize_text(raw_text)
    page_rect = page.rect
    width = max(0.0, float(page_rect.width))
    height = max(0.0, float(page_rect.height))
    image_count, image_area_ratio = _image_statistics(
        page,
        page_area=width * height,
    )

    warnings: list[str] = []
    if _detect_column_layout(horizontal_bands, width):
        warnings.append(
            f"Page {page_number} may use a multi-column layout; "
            "text order is approximate."
        )

    metadata: dict[str, JsonValue] = {
        "pageNumber": page_number,
        "width": width,
        "height": height,
        "rotation": int(page.rotation),
        "imageCount": image_count,
        "textBlockCount": len(blocks),
        "sourceTextBlockCount": text_source_number,
        "largestImageAreaRatio": image_area_ratio,
    }
    container = ExtractedContainerData(
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=page_number,
        name=f"Page {page_number}",
        title=None,
        raw_text=raw_text,
        normalised_text=normalised_text,
        character_count=count_characters(normalised_text),
        word_count=count_words(normalised_text),
        metadata=metadata,
        blocks=blocks,
        tables=[],
    )
    evidence = PDFPageScanEvidence(
        page_number=page_number,
        character_count=container.character_count,
        text_block_count=len(blocks),
        image_count=image_count,
        largest_image_area_ratio=image_area_ratio,
    )
    return ExtractedPDFPage(
        container=container,
        scan_evidence=evidence,
        warnings=tuple(warnings),
    )


def _detect_column_layout(
    bands: list[tuple[float, float, float]],
    page_width: float,
) -> bool:
    """Flag obvious side-by-side text bands without claiming certainty."""
    if len(bands) < 4 or page_width <= 0:
        return False
    left = [band for band in bands if band[0] < page_width * 0.45]
    right = [band for band in bands if band[0] > page_width * 0.5]
    if len(left) < 2 or len(right) < 2:
        return False
    return any(
        max(left_band[1], right_band[1])
        < min(left_band[2], right_band[2])
        for left_band in left
        for right_band in right
    )
