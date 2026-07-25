"""Normalize DOCX style, heading, list, and break metadata."""

import re
from typing import Any

from docx.oxml.ns import qn

_HEADING_STYLE_PATTERN = re.compile(r"^heading\s+([1-9])$", re.IGNORECASE)


def style_name(paragraph: Any) -> str | None:
    """Return a bounded style name when one is assigned."""
    try:
        value = paragraph.style.name
    except (AttributeError, KeyError, ValueError):
        return None
    normalized = str(value).strip()
    return normalized[:255] if normalized else None


def heading_level(paragraph: Any) -> int | None:
    """Resolve Heading 1-9 names and OOXML outline levels."""
    normalized_style = style_name(paragraph)
    if normalized_style:
        match = _HEADING_STYLE_PATTERN.match(normalized_style)
        if match:
            return int(match.group(1))

    paragraph_properties = paragraph._p.pPr
    outline_level = (
        paragraph_properties.find(qn("w:outlineLvl"))
        if paragraph_properties is not None
        else None
    )
    if outline_level is None:
        return None
    raw_value = outline_level.get(qn("w:val"))
    try:
        numeric = int(raw_value)
    except (TypeError, ValueError):
        return None
    return numeric + 1 if 0 <= numeric <= 8 else None


def alignment_name(paragraph: Any) -> str | None:
    """Return the public enum name rather than an implementation integer."""
    alignment = paragraph.alignment
    if alignment is None:
        return None
    name = getattr(alignment, "name", None)
    return str(name) if name else str(alignment)


def list_metadata(paragraph: Any) -> tuple[bool, int | None, int | None]:
    """Return list membership, numbering ID, and indentation level."""
    properties = paragraph._p.pPr
    numbering = properties.numPr if properties is not None else None
    if numbering is None:
        return False, None, None
    numbering_id = (
        int(numbering.numId.val)
        if numbering.numId is not None and numbering.numId.val is not None
        else None
    )
    list_level = (
        int(numbering.ilvl.val)
        if numbering.ilvl is not None and numbering.ilvl.val is not None
        else None
    )
    return True, numbering_id, list_level


def has_explicit_page_break(paragraph: Any) -> bool:
    """Detect explicit and last-rendered page-break markers."""
    paragraph_element = paragraph._p
    for element in paragraph_element.iter():
        if element.tag == qn("w:lastRenderedPageBreak"):
            return True
        if (
            element.tag == qn("w:br")
            and element.get(qn("w:type")) == "page"
        ):
            return True
    return False
