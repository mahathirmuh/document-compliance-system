"""Public request and response contracts for extraction jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.extraction_job import ExtractionJobStatus, ExtractionJobType
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class ExtractionRequest(ApiSchema):
    """Queue an initial extraction or explicitly force a re-extraction."""

    document_file_id: UUID
    force: bool = False


class ReExtractionRequest(ApiSchema):
    """A human-readable reason is mandatory for retained re-extractions."""

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


class ExtractionDocumentReference(ApiSchema):
    id: UUID
    base_document_code: str
    title: str
    department_id: UUID


class ExtractionRevisionReference(ApiSchema):
    id: UUID
    revision_code: str
    full_document_code: str


class ExtractionFileReference(ApiSchema):
    id: UUID
    filename: str
    extension: str
    sha256_hash: str


class ExtractionRequesterReference(ApiSchema):
    id: UUID
    name: str


class ExtractionJobError(ApiSchema):
    code: str
    message: str


class ExtractionQueuedResponse(ApiSchema):
    job_id: UUID
    status: ExtractionJobStatus
    progress: int = Field(ge=0, le=100)
    document_file_id: UUID
    reused_existing_result: bool = False
    run_id: UUID | None = None


class ExtractionJobListItem(ApiSchema):
    id: UUID
    document: ExtractionDocumentReference
    revision: ExtractionRevisionReference
    file: ExtractionFileReference
    job_type: ExtractionJobType
    status: ExtractionJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    requested_by: ExtractionRequesterReference | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    run_id: UUID | None = None
    result_summary: dict[str, object] | None = None


class ExtractionJobDetailResponse(ExtractionJobListItem):
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    failed_at: datetime | None = None
    error: ExtractionJobError | None = None


class ExtractionCancelResponse(ApiSchema):
    id: UUID
    status: ExtractionJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    cancelled_at: datetime | None = None


class ExtractionJobListResponse(PaginationData[ExtractionJobListItem]):
    """Paginated queue/history data with backend department scoping."""

