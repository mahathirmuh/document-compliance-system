"""Paginated extracted containers, blocks, tables, and search responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.extracted_block import ExtractedBlockType
from app.models.extracted_container import ExtractedContainerType
from app.models.language_block_result import LanguageCode
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData

ExtractedContentSource = Literal["NATIVE", "OCR"]


class ExtractedContainerResponse(ApiSchema):
    """Lightweight metadata for paginated container API responses."""

    id: UUID
    extraction_run_id: UUID
    container_type: ExtractedContainerType
    container_index: int = Field(ge=0)
    name: str | None = None
    title: str | None = None
    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    metadata: dict[str, object] | None = None
    created_at: datetime


class ExtractedContainerExportResponse(ExtractedContainerResponse):
    """Full container content serialized only by the export path."""

    raw_text: str
    normalised_text: str


class ExtractedBlockResponse(ApiSchema):
    """One native or OCR viewer block with retained source provenance."""

    id: UUID
    extraction_run_id: UUID
    container_id: UUID
    parent_block_id: UUID | None = None
    block_type: ExtractedBlockType
    block_order: int = Field(ge=0)
    source_reference: str
    text: str
    normalised_text: str
    style_name: str | None = None
    heading_level: int | None = Field(default=None, ge=1, le=9)
    location: dict[str, object] | None = None
    metadata: dict[str, object] | None = None
    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    created_at: datetime
    content_source: ExtractedContentSource = "NATIVE"
    language_code: LanguageCode | None = None
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: dict[str, object] = Field(default_factory=dict)


class ExtractedTableCellResponse(ApiSchema):
    id: UUID
    extracted_table_id: UUID
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(ge=1)
    column_span: int = Field(ge=1)
    coordinate: str | None = None
    text: str
    normalised_text: str
    metadata: dict[str, object] | None = None
    created_at: datetime


class ExtractedTableResponse(ApiSchema):
    """Bounded table metadata and cells for paginated API responses."""

    id: UUID
    extraction_run_id: UUID
    container_id: UUID
    source_reference: str
    table_index: int = Field(ge=0)
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    metadata: dict[str, object] | None = None
    cells: list[ExtractedTableCellResponse] = Field(default_factory=list)
    created_at: datetime


class ExtractedTableExportResponse(ExtractedTableResponse):
    """Full table text serialized only by the export path."""

    raw_text: str


class ExtractedContentSearchItem(ApiSchema):
    block_id: UUID
    block_order: int = Field(ge=0)
    container_id: UUID
    container_index: int = Field(ge=0)
    container_name: str | None = None
    source_reference: str
    block_type: ExtractedBlockType
    snippet: str
    location: dict[str, object] | None = None


class ExtractedContentSearchResponse(ApiSchema):
    query: str
    total_matches: int = Field(ge=0)
    items: list[ExtractedContentSearchItem]


class ExtractedContainerListResponse(
    PaginationData[ExtractedContainerResponse]
):
    pass


class ExtractedBlockListResponse(PaginationData[ExtractedBlockResponse]):
    pass


class ExtractedTableListResponse(PaginationData[ExtractedTableResponse]):
    pass


ExtractionExportFormat = Literal["json", "txt"]
