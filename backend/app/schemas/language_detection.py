"""Public Phase 7 language detection API contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.extraction_job import ExtractionJobStatus
from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityReason,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.models.language_detection_job import (
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.models.language_detection_run import LanguageDetectionRunStatus
from app.models.ocr_job import OCRJobStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.language_internal import (
    CoverageBreakdownData,
    LanguagePresenceData,
)


class LanguageDetectionStartRequest(ApiSchema):
    document_file_id: UUID
    extraction_run_id: UUID
    ocr_run_id: UUID | None = None
    force: bool = False


class LanguageRedetectRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("Reason must not be empty.")
            return normalized
        return value


class LanguageDetectionQueuedResponse(ApiSchema):
    job_id: UUID
    status: LanguageDetectionJobStatus
    progress: int = Field(ge=0, le=100)
    document_file_id: UUID
    extraction_run_id: UUID
    ocr_run_id: UUID | None = None
    reused_existing_result: bool = False
    run_id: UUID | None = None


class LanguageJobDocumentReference(ApiSchema):
    id: UUID
    base_document_code: str
    title: str
    department_id: UUID


class LanguageJobRevisionReference(ApiSchema):
    id: UUID
    revision_code: str
    full_document_code: str


class LanguageJobFileReference(ApiSchema):
    id: UUID
    filename: str
    extension: str
    sha256_hash: str


class LanguageJobRequesterReference(ApiSchema):
    id: UUID
    name: str


class LanguageDetectionDocumentStatus(StrEnum):
    """Filter values for the document inventory."""

    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    LOADING_CONTENT = "LOADING_CONTENT"
    DETECTING = "DETECTING"
    AGGREGATING = "AGGREGATING"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class LanguageDetectionDocumentListItem(ApiSchema):
    """Current file and its real extraction, OCR, and language state."""

    document: LanguageJobDocumentReference
    revision: LanguageJobRevisionReference
    file: LanguageJobFileReference
    extraction_status: ExtractionJobStatus | None = None
    ocr_status: OCRJobStatus | None = None
    language_detection_status: LanguageDetectionJobStatus | None = None
    language_progress: int | None = Field(default=None, ge=0, le=100)
    language_current_stage: str | None = None
    extraction_run_id: UUID | None = None
    ocr_run_id: UUID | None = None
    language_detection_run_id: UUID | None = None
    language_presence: LanguagePresenceData | None = None
    last_detected: datetime | None = None
    source_ready: bool


class LanguageDetectionDocumentListResponse(
    PaginationData[LanguageDetectionDocumentListItem]
):
    pass


class LanguageDetectionJobError(ApiSchema):
    code: str
    message: str


class LanguageDetectionJobListItem(ApiSchema):
    id: UUID
    document: LanguageJobDocumentReference
    revision: LanguageJobRevisionReference
    file: LanguageJobFileReference
    extraction_run_id: UUID
    ocr_run_id: UUID | None = None
    job_type: LanguageDetectionJobType
    status: LanguageDetectionJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    requested_by: LanguageJobRequesterReference | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    run_id: UUID | None = None
    result_summary: dict[str, object] | None = None


class LanguageDetectionJobResponse(LanguageDetectionJobListItem):
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    failed_at: datetime | None = None
    error: LanguageDetectionJobError | None = None


class LanguageDetectionJobListResponse(PaginationData[LanguageDetectionJobListItem]):
    pass


class LanguageDetectionCancelResponse(ApiSchema):
    id: UUID
    status: LanguageDetectionJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    cancelled_at: datetime | None = None


class LanguagePresenceResponse(LanguagePresenceData):
    pass


class LanguageCoverageResponse(ApiSchema):
    block_coverage: CoverageBreakdownData
    character_coverage: CoverageBreakdownData
    preliminary: bool = True
    disclaimer: str = (
        "Coverage is preliminary language detection and does not represent "
        "translation equivalence or final compliance."
    )


class LanguageAverageConfidenceResponse(ApiSchema):
    id: float | None = Field(default=None, ge=0, le=1)
    en: float | None = Field(default=None, ge=0, le=1)
    zh: float | None = Field(default=None, ge=0, le=1)


class LanguageSummaryResponse(ApiSchema):
    run_id: UUID
    total_blocks: int = Field(ge=0)
    eligible_blocks: int = Field(ge=0)
    detected_blocks: int = Field(ge=0)
    unknown_blocks: int = Field(ge=0)
    mixed_blocks: int = Field(ge=0)
    indonesian_blocks: int = Field(ge=0)
    english_blocks: int = Field(ge=0)
    chinese_blocks: int = Field(ge=0)
    other_blocks: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    indonesian_characters: int = Field(ge=0)
    english_characters: int = Field(ge=0)
    chinese_characters: int = Field(ge=0)
    mixed_characters: int = Field(ge=0)
    unknown_characters: int = Field(ge=0)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    average_confidence_by_language: LanguageAverageConfidenceResponse
    language_presence: LanguagePresenceResponse
    coverage: LanguageCoverageResponse
    preliminary_label: str = "Preliminary Coverage"


class LanguageDetectionRunResponse(LanguageSummaryResponse):
    document_file_id: UUID
    document_id: UUID
    document_revision_id: UUID
    extraction_run_id: UUID
    ocr_run_id: UUID | None = None
    job_id: UUID
    detector_name: str
    detector_version: str
    status: LanguageDetectionRunStatus
    source_content_hash: str
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] | None = None
    requested_by: LanguageJobRequesterReference | None = None
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    is_latest: bool


class LanguageDetectionHistoryItem(ApiSchema):
    id: UUID
    job_id: UUID
    detector_name: str
    detector_version: str
    status: LanguageDetectionRunStatus
    source_content_hash: str
    total_blocks: int = Field(ge=0)
    detected_blocks: int = Field(ge=0)
    unknown_blocks: int = Field(ge=0)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    requested_by: LanguageJobRequesterReference | None = None
    redetection_reason: str | None = None
    completed_at: datetime
    is_latest: bool


class LanguageBlockResultResponse(ApiSchema):
    id: UUID
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    container_id: UUID | None = None
    source_type: LanguageSourceType
    source_reference: str
    text: str
    language_code: LanguageCode
    primary_language_code: LanguageCode
    confidence: float = Field(ge=0, le=1)
    is_mixed: bool
    detected_languages: list[dict[str, object]]
    script_statistics: dict[str, object]
    eligibility_status: LanguageEligibilityStatus
    eligibility_reason: LanguageEligibilityReason | None = None
    character_count: int = Field(ge=0)
    latin_character_count: int = Field(ge=0)
    han_character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    source_confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, object] | None = None
    created_at: datetime


class LanguageBlockResultListResponse(PaginationData[LanguageBlockResultResponse]):
    pass


class LanguageContainerSummaryResponse(ApiSchema):
    id: UUID
    container_id: UUID | None = None
    container_type: str
    container_name: str | None = None
    container_index: int = Field(ge=0)
    total_blocks: int = Field(ge=0)
    eligible_blocks: int = Field(ge=0)
    indonesian_blocks: int = Field(ge=0)
    english_blocks: int = Field(ge=0)
    chinese_blocks: int = Field(ge=0)
    mixed_blocks: int = Field(ge=0)
    unknown_blocks: int = Field(ge=0)
    other_blocks: int = Field(ge=0)
    indonesian_characters: int = Field(ge=0)
    english_characters: int = Field(ge=0)
    chinese_characters: int = Field(ge=0)
    mixed_characters: int = Field(ge=0)
    unknown_characters: int = Field(ge=0)
    dominant_language: LanguageCode
    language_presence: dict[str, object]
    coverage: dict[str, object]
    created_at: datetime


class LanguageContainerSummaryListResponse(
    PaginationData[LanguageContainerSummaryResponse]
):
    pass


LanguageExportFormat = Literal["json", "xlsx"]
