"""Paragraph and heading extraction including hyperlink text in XML order."""

from typing import Any

from docx.oxml.ns import qn
from pydantic import JsonValue

from app.schemas.extraction import ExtractedBlockData, ExtractedBlockType
from app.services.extraction.docx.docx_style_normalizer import (
    alignment_name,
    has_explicit_page_break,
    heading_level,
    list_metadata,
    style_name,
)
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)


def paragraph_text(paragraph: Any) -> str:
    """Read text, tabs, and line breaks from descendants in source order."""
    output: list[str] = []
    for element in paragraph._p.iter():
        if element.tag == qn("w:t"):
            output.append(element.text or "")
        elif element.tag == qn("w:tab"):
            output.append("\t")
        elif element.tag == qn("w:br"):
            output.append("\n")
    return "".join(output)


def extract_docx_paragraph(
    paragraph: Any,
    *,
    paragraph_index: int,
    block_order: int,
    block_type_override: ExtractedBlockType | None = None,
    source_prefix: str = "DOCX",
) -> ExtractedBlockData | None:
    """Normalize one paragraph while preserving its source index."""
    text = paragraph_text(paragraph)
    normalised_text = normalize_text(text)
    page_break = has_explicit_page_break(paragraph)
    if not normalised_text and not page_break:
        return None

    level = heading_level(paragraph) if block_type_override is None else None
    block_type = block_type_override or (
        ExtractedBlockType.HEADING
        if level is not None
        else ExtractedBlockType.PARAGRAPH
    )
    is_list_item, numbering_id, list_level = list_metadata(paragraph)
    metadata: dict[str, JsonValue] = {
        "paragraphIndex": paragraph_index,
        "styleName": style_name(paragraph),
        "alignment": alignment_name(paragraph),
        "isListItem": is_list_item,
        "numberingId": numbering_id,
        "listLevel": list_level,
        "hasPageBreak": page_break,
    }
    return ExtractedBlockData(
        block_type=block_type,
        block_order=block_order,
        source_reference=f"{source_prefix}:paragraph={paragraph_index}",
        text=text,
        normalised_text=normalised_text,
        style_name=style_name(paragraph),
        heading_level=level,
        location={"paragraphIndex": paragraph_index},
        metadata=metadata,
        character_count=count_characters(normalised_text),
        word_count=count_words(normalised_text),
    )
