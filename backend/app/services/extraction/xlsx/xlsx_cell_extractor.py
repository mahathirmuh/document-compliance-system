"""Convert one openpyxl cell into a unified extraction block."""

from typing import Any

from openpyxl.utils import get_column_letter
from pydantic import JsonValue

from app.schemas.extraction import ExtractedBlockData, ExtractedBlockType
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)
from app.services.extraction.xlsx.xlsx_formula_normalizer import (
    display_xlsx_value,
    formula_metadata,
    serialize_xlsx_value,
)
from app.services.extraction.xlsx.xlsx_merge_extractor import XLSXMergedRange


def extract_xlsx_cell(
    cell: Any,
    cached_cell: Any | None,
    *,
    sheet_name: str,
    block_order: int,
    merged_range: XLSXMergedRange | None,
    row_hidden: bool,
    column_hidden: bool,
    hyperlink_target: str | None = None,
) -> ExtractedBlockData | None:
    """Extract a non-empty cell or a declared merged-range anchor."""
    value = cell.value
    if value is None and merged_range is None:
        return None

    cached_value = cached_cell.value if cached_cell is not None else None
    is_formula = str(getattr(cell, "data_type", "")) == "f"
    if merged_range is not None:
        block_type = ExtractedBlockType.MERGED_CELL
    elif is_formula:
        block_type = ExtractedBlockType.FORMULA
    else:
        block_type = ExtractedBlockType.CELL

    text = display_xlsx_value(value)
    normalised_text = normalize_text(text)
    hyperlink = getattr(cell, "hyperlink", None)
    cell_hyperlink_target = getattr(hyperlink, "target", None)
    effective_hyperlink_target = hyperlink_target or cell_hyperlink_target
    column_number = int(cell.column)
    metadata: dict[str, JsonValue] = {
        "sheet": sheet_name,
        "coordinate": str(cell.coordinate),
        "row": int(cell.row),
        "column": column_number,
        "dataType": str(getattr(cell, "data_type", "")),
        "numberFormat": str(getattr(cell, "number_format", "General")),
        "rawValue": serialize_xlsx_value(value),
        "isFormula": is_formula,
        "isMerged": merged_range is not None,
        "hyperlink": (
            str(effective_hyperlink_target)
            if effective_hyperlink_target
            else None
        ),
        "hyperlinkFollowed": False,
        "rowHidden": row_hidden,
        "columnHidden": column_hidden,
    }
    if is_formula:
        metadata.update(formula_metadata(value, cached_value))
    if merged_range is not None:
        metadata.update(
            {
                "range": merged_range.reference,
                "startCell": merged_range.start_cell,
                "endCell": merged_range.end_cell,
                "rowSpan": merged_range.row_span,
                "columnSpan": merged_range.column_span,
            }
        )

    return ExtractedBlockData(
        block_type=block_type,
        block_order=block_order,
        source_reference=(
            f"XLSX:sheet={sheet_name}:cell={cell.coordinate}"
        ),
        text=text,
        normalised_text=normalised_text,
        location={
            "sheet": sheet_name,
            "row": int(cell.row),
            "column": column_number,
            "columnLetter": get_column_letter(column_number),
            "coordinate": str(cell.coordinate),
        },
        metadata=metadata,
        character_count=count_characters(normalised_text),
        word_count=count_words(normalised_text),
    )
