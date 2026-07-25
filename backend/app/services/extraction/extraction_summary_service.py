"""Format-neutral extraction summary calculation."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.extraction import (
    ExtractedBlockType,
    ExtractedContainerType,
    ExtractedDocumentData,
)


@dataclass(frozen=True, slots=True)
class ExtractionSummary:
    """Counts persisted on an extraction run and returned by the API."""

    total_pages: int
    total_sheets: int
    total_blocks: int
    total_paragraphs: int
    total_tables: int
    total_cells: int
    total_characters: int
    total_words: int

    def as_dict(self) -> dict[str, int]:
        return {
            "totalPages": self.total_pages,
            "totalSheets": self.total_sheets,
            "totalBlocks": self.total_blocks,
            "totalParagraphs": self.total_paragraphs,
            "totalTables": self.total_tables,
            "totalCells": self.total_cells,
            "totalCharacters": self.total_characters,
            "totalWords": self.total_words,
        }


class ExtractionSummaryService:
    """Calculate totals once, without double-counting table search blocks."""

    @staticmethod
    def calculate(result: ExtractedDocumentData) -> ExtractionSummary:
        blocks = [
            block
            for container in result.containers
            for block in container.blocks
        ]
        tables = [
            table
            for container in result.containers
            for table in container.tables
        ]
        structured_cells = sum(len(table.cells) for table in tables)
        xlsx_cells = sum(
            block.block_type
            in {
                ExtractedBlockType.CELL,
                ExtractedBlockType.FORMULA,
                ExtractedBlockType.MERGED_CELL,
            }
            for block in blocks
        )
        return ExtractionSummary(
            total_pages=sum(
                container.container_type == ExtractedContainerType.PDF_PAGE
                for container in result.containers
            ),
            total_sheets=sum(
                container.container_type
                == ExtractedContainerType.XLSX_WORKSHEET
                for container in result.containers
            ),
            total_blocks=len(blocks),
            total_paragraphs=sum(
                block.block_type
                in {
                    ExtractedBlockType.PARAGRAPH,
                    ExtractedBlockType.HEADING,
                }
                for block in blocks
            ),
            total_tables=len(tables),
            total_cells=(
                xlsx_cells
                if result.extractor_type == "XLSX"
                else structured_cells
            ),
            total_characters=sum(
                container.character_count for container in result.containers
            ),
            total_words=sum(
                container.word_count for container in result.containers
            ),
        )

