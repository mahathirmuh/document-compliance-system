"""Structured DOCX table and merged-cell extraction."""

from dataclasses import dataclass
from typing import Any

from app.schemas.extraction import (
    ExtractedBlockData,
    ExtractedBlockType,
    ExtractedTableCellData,
    ExtractedTableData,
)
from app.services.extraction.base_extractor import ExtractionResourceLimitError
from app.services.extraction.docx.docx_paragraph_extractor import paragraph_text
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)


@dataclass(frozen=True, slots=True)
class ExtractedDOCXTable:
    """One structured table plus unified search blocks."""

    table: ExtractedTableData
    blocks: tuple[ExtractedBlockData, ...]
    next_block_order: int
    logical_cell_count: int


def extract_docx_table(
    table: Any,
    *,
    table_index: int,
    block_order: int,
    source_prefix: str = "DOCX",
    maximum_logical_cells: int | None = None,
) -> ExtractedDOCXTable:
    """Extract logical merged cells without duplicating their text."""
    matrix = [[cell for cell in row.cells] for row in table.rows]
    row_count = len(matrix)
    column_count = max((len(row) for row in matrix), default=0)
    positions_by_cell: dict[int, list[tuple[int, int]]] = {}
    cell_by_identity: dict[int, Any] = {}
    for row_index, row in enumerate(matrix, start=1):
        for column_index, cell in enumerate(row, start=1):
            identity = id(cell._tc)
            if (
                identity not in positions_by_cell
                and maximum_logical_cells is not None
                and len(positions_by_cell) >= maximum_logical_cells
            ):
                raise ExtractionResourceLimitError(
                    "DOCX_EXTRACTION_FAILED",
                    "The DOCX exceeds the configured table-cell limit.",
                    details={
                        "remainingTableCells": maximum_logical_cells,
                    },
                )
            positions_by_cell.setdefault(identity, []).append(
                (row_index, column_index)
            )
            cell_by_identity[identity] = cell

    table_reference = f"{source_prefix}:table={table_index}"
    table_block_order = block_order
    blocks: list[ExtractedBlockData] = [
        ExtractedBlockData(
            block_type=ExtractedBlockType.TABLE,
            block_order=table_block_order,
            source_reference=table_reference,
            text="",
            normalised_text="",
            location={"tableIndex": table_index},
            metadata={
                "tableIndex": table_index,
                "rowCount": row_count,
                "columnCount": column_count,
            },
            character_count=0,
            word_count=0,
        )
    ]
    next_order = table_block_order + 1
    cells: list[ExtractedTableCellData] = []
    row_texts: dict[int, list[str]] = {}
    ordered_cells = sorted(
        positions_by_cell.items(),
        key=lambda item: min(item[1]),
    )
    for identity, positions in ordered_cells:
        row_index = min(position[0] for position in positions)
        column_index = min(position[1] for position in positions)
        row_span = max(position[0] for position in positions) - row_index + 1
        column_span = (
            max(position[1] for position in positions) - column_index + 1
        )
        cell = cell_by_identity[identity]
        text = "\n".join(paragraph_text(item) for item in cell.paragraphs)
        normalised_text = normalize_text(text)
        coordinate = f"R{row_index}C{column_index}"
        cell_metadata = {
            "tableIndex": table_index,
            "rowIndex": row_index,
            "columnIndex": column_index,
            "rowSpan": row_span,
            "columnSpan": column_span,
            "hasNestedTable": bool(cell.tables),
        }
        cells.append(
            ExtractedTableCellData(
                row_index=row_index,
                column_index=column_index,
                row_span=row_span,
                column_span=column_span,
                coordinate=coordinate,
                text=text,
                normalised_text=normalised_text,
                metadata=cell_metadata,
            )
        )
        row_texts.setdefault(row_index, []).append(text)
        if normalised_text:
            blocks.append(
                ExtractedBlockData(
                    block_type=ExtractedBlockType.TABLE_CELL,
                    block_order=next_order,
                    parent_block_order=table_block_order,
                    source_reference=(
                        f"{table_reference}:row={row_index}:"
                        f"cell={column_index}"
                    ),
                    text=text,
                    normalised_text=normalised_text,
                    location={
                        "tableIndex": table_index,
                        "row": row_index,
                        "column": column_index,
                    },
                    metadata=cell_metadata,
                    character_count=count_characters(normalised_text),
                    word_count=count_words(normalised_text),
                )
            )
            next_order += 1

    raw_text = "\n".join(
        "\t".join(row_texts.get(index, []))
        for index in range(1, row_count + 1)
    )
    table_style = getattr(getattr(table, "style", None), "name", None)
    table_data = ExtractedTableData(
        source_reference=table_reference,
        table_index=table_index,
        row_count=row_count,
        column_count=column_count,
        raw_text=raw_text,
        metadata={
            "styleName": str(table_style) if table_style else None,
            "logicalCellCount": len(cells),
        },
        cells=cells,
    )
    return ExtractedDOCXTable(
        table=table_data,
        blocks=tuple(blocks),
        next_block_order=next_order,
        logical_cell_count=len(cells),
    )
