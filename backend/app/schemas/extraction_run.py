"""Public summaries and history contracts for extraction runs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.extraction_run import ExtractionRunStatus, ExtractorType
from app.schemas.base import ApiSchema
from app.schemas.extraction_job import (
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)


class ExtractionRunSummary(ApiSchema):
    run_id: UUID
    status: ExtractionRunStatus
    extractor_type: ExtractorType
    total_pages: int = Field(ge=0)
    total_sheets: int = Field(ge=0)
    total_blocks: int = Field(ge=0)
    total_paragraphs: int = Field(ge=0)
    total_tables: int = Field(ge=0)
    total_cells: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    total_words: int = Field(ge=0)
    has_selectable_text: bool
    requires_ocr: bool
    warnings: list[str] = Field(default_factory=list)


class ExtractionRunResponse(ExtractionRunSummary):
    extraction_job_id: UUID
    document: ExtractionDocumentReference
    revision: ExtractionRevisionReference
    file: ExtractionFileReference
    extractor_version: str
    source_sha256_hash: str
    source_file_size: int = Field(ge=0)
    content_hash: str | None = None
    metadata: dict[str, object] | None = None
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    is_latest: bool


class ExtractionRunHistoryItem(ApiSchema):
    id: UUID
    extraction_job_id: UUID
    extractor_type: ExtractorType
    extractor_version: str
    status: ExtractionRunStatus
    source_sha256_hash: str
    content_hash: str | None = None
    summary: ExtractionRunSummary
    requested_by: ExtractionRequesterReference | None = None
    re_extraction_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    completed_at: datetime
    is_latest: bool

