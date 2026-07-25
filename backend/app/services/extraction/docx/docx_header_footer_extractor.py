"""DOCX header/footer containers with linked-section references."""

from dataclasses import dataclass
from typing import Any

from app.schemas.extraction import (
    ExtractedBlockType,
    ExtractedContainerData,
    ExtractedContainerType,
    ExtractionContext,
)
from app.services.extraction.base_extractor import ExtractionResourceLimitError
from app.services.extraction.docx.docx_element_iterator import iter_docx_elements
from app.services.extraction.docx.docx_paragraph_extractor import (
    extract_docx_paragraph,
)
from app.services.extraction.docx.docx_table_extractor import extract_docx_table
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)


@dataclass(frozen=True, slots=True)
class HeaderFooterExtraction:
    """Containers and resource counts contributed by headers/footers."""

    containers: tuple[ExtractedContainerData, ...]
    paragraph_count: int
    table_count: int
    table_cell_count: int
    next_container_index: int


def extract_headers_and_footers(
    document: Any,
    *,
    first_container_index: int,
    context: ExtractionContext,
    starting_paragraph_count: int,
    starting_table_count: int,
    starting_table_cell_count: int,
) -> HeaderFooterExtraction:
    containers: list[ExtractedContainerData] = []
    paragraph_count = 0
    table_count = 0
    table_cell_count = 0
    container_index = first_container_index
    part_definitions = (
        ("default", "header", ExtractedContainerType.DOCX_HEADER),
        ("first_page", "first_page_header", ExtractedContainerType.DOCX_HEADER),
        ("even_page", "even_page_header", ExtractedContainerType.DOCX_HEADER),
        ("default", "footer", ExtractedContainerType.DOCX_FOOTER),
        ("first_page", "first_page_footer", ExtractedContainerType.DOCX_FOOTER),
        ("even_page", "even_page_footer", ExtractedContainerType.DOCX_FOOTER),
    )
    for section_index, section in enumerate(document.sections, start=1):
        for variant, attribute_name, container_type in part_definitions:
            part = getattr(section, attribute_name)
            linked = bool(part.is_linked_to_previous)
            if linked and section_index == 1:
                continue
            if linked:
                containers.append(
                    _linked_container(
                        container_type=container_type,
                        container_index=container_index,
                        section_index=section_index,
                        variant=variant,
                    )
                )
                container_index += 1
                continue

            blocks = []
            tables = []
            raw_parts: list[str] = []
            block_order = 1
            local_paragraph_index = 0
            local_table_index = 0
            source_kind = (
                "header"
                if container_type is ExtractedContainerType.DOCX_HEADER
                else "footer"
            )
            block_type = (
                ExtractedBlockType.HEADER
                if source_kind == "header"
                else ExtractedBlockType.FOOTER
            )
            source_prefix = (
                f"DOCX:section={section_index}:{source_kind}={variant}"
            )
            for element_kind, element in iter_docx_elements(part):
                if element_kind == "paragraph":
                    paragraph_count += 1
                    _enforce_header_footer_limits(
                        context,
                        paragraphs=starting_paragraph_count + paragraph_count,
                        tables=starting_table_count + table_count,
                        cells=starting_table_cell_count + table_cell_count,
                    )
                    local_paragraph_index += 1
                    block = extract_docx_paragraph(
                        element,
                        paragraph_index=local_paragraph_index,
                        block_order=block_order,
                        block_type_override=block_type,
                        source_prefix=source_prefix,
                    )
                    if block is not None:
                        blocks.append(block)
                        raw_parts.append(block.text)
                        block_order += 1
                else:
                    table_count += 1
                    _enforce_header_footer_limits(
                        context,
                        paragraphs=starting_paragraph_count + paragraph_count,
                        tables=starting_table_count + table_count,
                        cells=starting_table_cell_count + table_cell_count,
                    )
                    local_table_index += 1
                    result = extract_docx_table(
                        element,
                        table_index=local_table_index,
                        block_order=block_order,
                        source_prefix=source_prefix,
                        maximum_logical_cells=max(
                            0,
                            context.docx_max_table_cells
                            - starting_table_cell_count
                            - table_cell_count,
                        ),
                    )
                    tables.append(result.table)
                    blocks.extend(result.blocks)
                    raw_parts.append(result.table.raw_text)
                    table_cell_count += result.logical_cell_count
                    _enforce_header_footer_limits(
                        context,
                        paragraphs=starting_paragraph_count + paragraph_count,
                        tables=starting_table_count + table_count,
                        cells=starting_table_cell_count + table_cell_count,
                    )
                    block_order = result.next_block_order

            raw_text = "\n".join(part for part in raw_parts if part)
            if not normalize_text(raw_text):
                continue
            normalised_text = normalize_text(raw_text)
            containers.append(
                ExtractedContainerData(
                    container_type=container_type,
                    container_index=container_index,
                    name=(
                        f"section-{section_index}-{variant}-"
                        f"{source_kind}"
                    ),
                    title=None,
                    raw_text=raw_text,
                    normalised_text=normalised_text,
                    character_count=count_characters(normalised_text),
                    word_count=count_words(normalised_text),
                    metadata={
                        "sectionIndex": section_index,
                        f"{source_kind}Type": variant,
                        "linkedToPrevious": False,
                    },
                    blocks=blocks,
                    tables=tables,
                )
            )
            container_index += 1

    return HeaderFooterExtraction(
        containers=tuple(containers),
        paragraph_count=paragraph_count,
        table_count=table_count,
        table_cell_count=table_cell_count,
        next_container_index=container_index,
    )


def _enforce_header_footer_limits(
    context: ExtractionContext,
    *,
    paragraphs: int,
    tables: int,
    cells: int,
) -> None:
    limits = (
        (
            paragraphs,
            context.docx_max_paragraphs,
            "paragraph",
        ),
        (tables, context.docx_max_tables, "table"),
        (cells, context.docx_max_table_cells, "table-cell"),
    )
    for actual, maximum, label in limits:
        if actual > maximum:
            raise ExtractionResourceLimitError(
                "DOCX_EXTRACTION_FAILED",
                f"The DOCX exceeds the configured {label} limit.",
                details={
                    "limitType": label,
                    "maximum": maximum,
                    "actual": actual,
                },
            )


def _linked_container(
    *,
    container_type: ExtractedContainerType,
    container_index: int,
    section_index: int,
    variant: str,
) -> ExtractedContainerData:
    source_kind = (
        "header"
        if container_type is ExtractedContainerType.DOCX_HEADER
        else "footer"
    )
    return ExtractedContainerData(
        container_type=container_type,
        container_index=container_index,
        name=f"section-{section_index}-{variant}-{source_kind}",
        title=None,
        raw_text="",
        normalised_text="",
        character_count=0,
        word_count=0,
        metadata={
            "sectionIndex": section_index,
            f"{source_kind}Type": variant,
            "linkedToPrevious": True,
            "linkedSectionIndex": section_index - 1,
        },
        blocks=[],
        tables=[],
    )
