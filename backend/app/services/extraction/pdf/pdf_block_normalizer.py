"""Convert PyMuPDF dictionary blocks into unified extraction blocks."""

import math
from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from app.schemas.extraction import ExtractedBlockData, ExtractedBlockType
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)


def _finite_float(value: object, *, default: float = 0.0) -> float:
    try:
        converted = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return converted if math.isfinite(converted) else default


def normalize_bbox(value: object) -> tuple[float, float, float, float]:
    """Return a finite, non-negative-width PDF rectangle."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return (0.0, 0.0, 0.0, 0.0)
    coordinates = list(value)
    if len(coordinates) != 4:
        return (0.0, 0.0, 0.0, 0.0)
    x0, y0, x1, y1 = (_finite_float(item) for item in coordinates)
    return (x0, y0, max(x0, x1), max(y0, y1))


def block_text(block: Mapping[str, object]) -> str:
    """Rebuild textual lines and spans without interpreting layout."""
    raw_lines = block.get("lines", [])
    if not isinstance(raw_lines, list):
        return ""

    lines: list[str] = []
    for line in raw_lines:
        if not isinstance(line, Mapping):
            continue
        spans = line.get("spans", [])
        if not isinstance(spans, list):
            continue
        line_text = "".join(
            str(span.get("text", ""))
            for span in spans
            if isinstance(span, Mapping)
        )
        lines.append(line_text)
    return "\n".join(lines)


def normalize_pdf_block(
    block: Mapping[str, object],
    *,
    page_number: int,
    source_block_number: int,
    block_order: int,
) -> ExtractedBlockData | None:
    """Create a unified text block, omitting non-text and empty blocks."""
    if block.get("type") != 0:
        return None
    text = block_text(block)
    normalised_text = normalize_text(text)
    if not normalised_text:
        return None

    x0, y0, x1, y1 = normalize_bbox(block.get("bbox"))
    location: dict[str, JsonValue] = {
        "page": page_number,
        "bbox": [x0, y0, x1, y1],
        "x": x0,
        "y": y0,
        "width": x1 - x0,
        "height": y1 - y0,
    }
    return ExtractedBlockData(
        block_type=ExtractedBlockType.TEXT,
        block_order=block_order,
        source_reference=(
            f"PDF:page={page_number}:block={source_block_number}"
        ),
        text=text,
        normalised_text=normalised_text,
        location=location,
        metadata={},
        character_count=count_characters(normalised_text),
        word_count=count_words(normalised_text),
    )
