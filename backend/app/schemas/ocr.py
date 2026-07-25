"""Public OCR request, result, history, and export contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.ocr_job import (
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_page_result import OCRPageStatus
from app.models.ocr_run import OCRRunStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.extraction_job import (
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)
from app.schemas.ocr_internal import OCRBoundingBox


def _unique_pages(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    if len(value) != len(set(value)):
        raise ValueError("Page numbers must be unique.")
    return sorted(value)


class OCRStartRequest(ApiSchema):
    """Queue OCR for selected or automatically detected PDF pages."""

    document_file_id: UUID
    extraction_run_id: UUID
    language_profile: OCRLanguageProfile = OCRLanguageProfile.AUTO_MULTILINGUAL
    page_numbers: list[int] | None = Field(
        default=None,
        min_length=1,
    )
    preprocessing_profile: OCRPreprocessingProfile = OCRPreprocessingProfile.STANDARD
    force: bool = False

    _validate_pages = field_validator("page_numbers")(_unique_pages)


class OCRReprocessRequest(ApiSchema):
    """Create a new OCR run without overwriting prior history."""

    reason: str = Field(min_length=1, max_length=1000)
    page_numbers: list[int] | None = Field(
        default=None,
        min_length=1,
    )
    language_profile: OCRLanguageProfile | None = None
    preprocessing_profile: OCRPreprocessingProfile | None = None

    _validate_pages = field_validator("page_numbers")(_unique_pages)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("Reason must not be empty.")
            return normalized
        return value


class OCRExportRequest(ApiSchema):
    """Supported export formats; PDF export is intentionally excluded."""

    format: Literal["json", "txt"] = "json"


class OCRJobError(ApiSchema):
    code: str
    message: str


class OCRQueuedResponse(ApiSchema):
    job_id: UUID
    status: OCRJobStatus
    progress: int = Field(ge=0, le=100)
    page_numbers: list[int]
    document_file_id: UUID
    run_id: UUID | None = None


class OCRJobListItem(ApiSchema):
    id: UUID
    document: ExtractionDocumentReference
    revision: ExtractionRevisionReference
    file: ExtractionFileReference
    extraction_run_id: UUID
    job_type: OCRJobType
    status: OCRJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    language_profile: OCRLanguageProfile
    preprocessing_profile: OCRPreprocessingProfile
    provider: str
    provider_version: str | None = None
    page_numbers: list[int]
    processed_page_numbers: list[int]
    failed_page_numbers: list[int]
    requested_by: ExtractionRequesterReference | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    run_id: UUID | None = None
    result_summary: dict[str, Any] | None = None


class OCRJobResponse(OCRJobListItem):
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    failed_at: datetime | None = None
    error: OCRJobError | None = None


class OCRCancelResponse(ApiSchema):
    id: UUID
    status: OCRJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    cancelled_at: datetime | None = None


class OCRSummary(ApiSchema):
    run_id: UUID
    status: OCRRunStatus
    page_count_requested: int = Field(ge=0)
    page_count_processed: int = Field(ge=0)
    page_count_failed: int = Field(ge=0)
    total_blocks: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    minimum_confidence: float | None = Field(default=None, ge=0, le=1)
    maximum_confidence: float | None = Field(default=None, ge=0, le=1)
    low_confidence_blocks: int = Field(default=0, ge=0)
    low_confidence_threshold: float = Field(default=0.60, ge=0, le=1)
    review_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class OCRRunResponse(OCRSummary):
    ocr_job_id: UUID
    source_extraction_run_id: UUID
    document: ExtractionDocumentReference
    revision: ExtractionRevisionReference
    file: ExtractionFileReference
    provider: str
    provider_version: str | None = None
    language_profile: OCRLanguageProfile
    source_sha256_hash: str
    render_dpi: int = Field(ge=72)
    preprocessing_profile: OCRPreprocessingProfile
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    is_latest: bool


class OCRRunHistoryItem(ApiSchema):
    id: UUID
    ocr_job_id: UUID
    source_extraction_run_id: UUID
    status: OCRRunStatus
    provider: str
    provider_version: str | None = None
    language_profile: OCRLanguageProfile
    preprocessing_profile: OCRPreprocessingProfile
    summary: OCRSummary
    requested_by: ExtractionRequesterReference | None = None
    re_ocr_reason: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    is_latest: bool


class OCRPageResultResponse(ApiSchema):
    id: UUID
    ocr_run_id: UUID
    page_number: int = Field(ge=1)
    status: OCRPageStatus
    language_profile: OCRLanguageProfile
    render_width: int = Field(ge=0)
    render_height: int = Field(ge=0)
    render_dpi: int = Field(ge=72)
    rotation_applied: int
    deskew_angle: float | None = None
    block_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    minimum_confidence: float | None = Field(default=None, ge=0, le=1)
    maximum_confidence: float | None = Field(default=None, ge=0, le=1)
    raw_text: str
    normalised_text: str
    content_hash: str | None = None
    warning_codes: list[str] = Field(default_factory=list)
    error: OCRJobError | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime

    @field_validator("rotation_applied")
    @classmethod
    def validate_rotation(cls, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("OCR rotation must be 0, 90, 180, or 270.")
        return value


class OCRBlockResponse(ApiSchema):
    id: UUID
    ocr_run_id: UUID
    ocr_page_result_id: UUID
    page_number: int = Field(ge=1)
    block_order: int = Field(ge=0)
    text: str
    normalised_text: str
    confidence: float = Field(ge=0, le=1)
    polygon: list[list[float]]
    bbox: OCRBoundingBox
    provider_model: str
    recognition_profile: str
    orientation: int
    metadata: dict[str, Any] | None = None
    character_count: int = Field(ge=0)
    created_at: datetime


class OCRPageListResponse(PaginationData[OCRPageResultResponse]):
    """Paginated page results ordered by PDF page."""


class OCRBlockListResponse(PaginationData[OCRBlockResponse]):
    """Paginated OCR blocks with optional confidence/page filtering."""


class OCRJobListResponse(PaginationData[OCRJobListItem]):
    """Paginated OCR queue/history with backend department scope."""


class OCRRunHistoryResponse(PaginationData[OCRRunHistoryItem]):
    """Paginated immutable OCR history."""


class OCRPageDetailResponse(ApiSchema):
    page: OCRPageResultResponse
    blocks: list[OCRBlockResponse]

    @model_validator(mode="after")
    def validate_block_page(self) -> OCRPageDetailResponse:
        if any(block.ocr_page_result_id != self.page.id for block in self.blocks):
            raise ValueError("OCR detail contains blocks from another page.")
        return self
