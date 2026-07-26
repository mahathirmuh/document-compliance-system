"""Public Phase 9 glossary validation job, result, and match contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossarySourceType,
    GlossaryValidationJobType,
    GlossaryValidationStatus,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class GlossaryValidationRequest(ApiSchema):
    document_file_id: UUID
    compliance_run_id: UUID | None = None
    profile_ids: list[UUID] = Field(default_factory=list, max_length=100)
    force: bool = False

    @field_validator("profile_ids")
    @classmethod
    def deduplicate_profiles(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class GlossaryRevalidationRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=2000)
    profile_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_is_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reason must not be empty.")
        return normalized

    @field_validator("profile_ids")
    @classmethod
    def deduplicate_profiles(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class GlossaryValidationQueuedResponse(ApiSchema):
    job_id: UUID
    run_id: UUID
    status: GlossaryValidationStatus
    progress: int = Field(ge=0, le=100)
    document_file_id: UUID
    reused_existing_result: bool = False


class GlossaryValidationRunResponse(ApiSchema):
    id: UUID
    job_id: UUID
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    compliance_run_id: UUID | None
    language_detection_run_id: UUID
    glossary_profile_ids: list[UUID]
    profile_snapshots: list[dict[str, Any]]
    job_type: GlossaryValidationJobType
    status: GlossaryValidationStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None
    source_content_hash: str
    total_terms: int = Field(ge=0)
    matched_terms: int = Field(ge=0)
    preferred_term_matches: int = Field(ge=0)
    forbidden_term_matches: int = Field(ge=0)
    missing_required_translations: int = Field(ge=0)
    inconsistent_terms: int = Field(ge=0)
    exception_applied_count: int = Field(ge=0)
    total_findings: int = Field(ge=0)
    metrics: dict[str, Any]
    warnings: list[str] | list[dict[str, Any]]
    error_code: str | None
    error_message: str | None
    requested_by: UUID | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancel_requested_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GlossaryValidationJobListResponse(
    PaginationData[GlossaryValidationRunResponse]
):
    pass


class GlossaryValidationSummaryResponse(ApiSchema):
    run_id: UUID
    status: GlossaryValidationStatus
    total_terms: int = Field(ge=0)
    matched_terms: int = Field(ge=0)
    preferred_term_matches: int = Field(ge=0)
    forbidden_term_matches: int = Field(ge=0)
    missing_required_translations: int = Field(ge=0)
    inconsistent_terms: int = Field(ge=0)
    exception_applied_count: int = Field(ge=0)
    total_findings: int = Field(ge=0)
    match_count: int = Field(ge=0)
    language_counts: dict[str, int] = Field(default_factory=dict)
    finding_counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] | list[dict[str, Any]] = Field(default_factory=list)


class GlossaryMatchResponse(ApiSchema):
    id: UUID
    glossary_validation_run_id: UUID
    glossary_term_id: UUID
    glossary_translation_id: UUID | None
    glossary_variant_id: UUID | None
    term_code: str | None = None
    concept_name: str | None = None
    language_code: GlossaryLanguageCode
    source_type: GlossarySourceType
    extracted_block_id: UUID | None
    ocr_block_id: UUID | None
    container_id: UUID | None
    detected_section_id: UUID | None
    source_reference: str
    matched_text: str
    normalised_matched_text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    match_type: GlossaryMatchType
    is_preferred: bool
    is_forbidden: bool
    exception_id: UUID | None
    metadata: dict[str, Any]
    created_at: datetime


class GlossaryMatchListResponse(PaginationData[GlossaryMatchResponse]):
    pass


class GlossaryValidationHistoryResponse(
    PaginationData[GlossaryValidationRunResponse]
):
    pass


class GlossaryFindingSignal(ApiSchema):
    """Finding data returned before/alongside Phase 8 workflow persistence."""

    id: UUID
    finding_code: str
    severity: str
    status: str
    title: str
    description: str
    recommendation: str
    glossary_term_id: UUID
    language_code: GlossaryLanguageCode | None = None
    source_reference: str | None = None
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    translation_group_id: UUID | None = None
    exception_id: UUID | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    is_repeat: bool = False
    previous_finding_id: UUID | None = None
    created_at: datetime


class GlossaryFindingListResponse(PaginationData[GlossaryFindingSignal]):
    pass
