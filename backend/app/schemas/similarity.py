"""Public camel-case API contracts for Phase 9 similarity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    SimilarityJobStatus,
    SimilarityJobType,
    SimilarityRunStatus,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


def _required_reason(value: object) -> object:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reason is required.")
    return value.strip()


class SimilarityStartRequest(ApiSchema):
    document_file_id: UUID
    compliance_run_id: UUID | None = None
    language_detection_run_id: UUID | None = None
    force: bool = False


class SimilarityRerunRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=2000)

    _reason = field_validator("reason", mode="before")(_required_reason)


class SimilarityDocumentReference(ApiSchema):
    id: UUID
    base_document_code: str
    title: str
    department_id: UUID


class SimilarityRevisionReference(ApiSchema):
    id: UUID
    revision_code: str
    full_document_code: str


class SimilarityFileReference(ApiSchema):
    id: UUID
    filename: str
    file_extension: str


class SimilarityRequesterReference(ApiSchema):
    id: UUID
    name: str


class SimilarityQueuedResponse(ApiSchema):
    id: UUID
    status: SimilarityJobStatus
    progress: int = Field(ge=0, le=100)
    document_file_id: UUID
    run_id: UUID | None = None
    reused_existing_result: bool = False


class SimilarityJobResponse(ApiSchema):
    id: UUID
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    compliance_run_id: UUID
    language_detection_run_id: UUID
    document: SimilarityDocumentReference | None = None
    revision: SimilarityRevisionReference | None = None
    file: SimilarityFileReference | None = None
    job_type: SimilarityJobType
    status: SimilarityJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    source_content_hash: str | None = None
    provider: str
    model_name: str
    requested_by: SimilarityRequesterReference | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
    result_summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SimilarityCancelResponse(ApiSchema):
    id: UUID
    status: SimilarityJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    cancelled_at: datetime | None = None


class SimilarityJobListResponse(PaginationData[SimilarityJobResponse]):
    pass


class SimilarityRunResponse(ApiSchema):
    id: UUID
    similarity_job_id: UUID
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    compliance_run_id: UUID
    language_detection_run_id: UUID
    document: SimilarityDocumentReference | None = None
    revision: SimilarityRevisionReference | None = None
    file: SimilarityFileReference | None = None
    provider: str
    model_name: str
    model_version: str | None = None
    status: SimilarityRunStatus
    source_content_hash: str
    translation_group_count: int = Field(ge=0)
    eligible_group_count: int = Field(ge=0)
    analysed_group_count: int = Field(ge=0)
    skipped_group_count: int = Field(ge=0)
    failed_group_count: int = Field(ge=0)
    average_similarity: float | None = Field(default=None, ge=0, le=1)
    minimum_similarity: float | None = Field(default=None, ge=0, le=1)
    maximum_similarity: float | None = Field(default=None, ge=0, le=1)
    id_en_average_similarity: float | None = Field(
        default=None, ge=0, le=1
    )
    id_zh_average_similarity: float | None = Field(
        default=None, ge=0, le=1
    )
    en_zh_average_similarity: float | None = Field(
        default=None, ge=0, le=1
    )
    high_similarity_groups: int = Field(ge=0)
    review_similarity_groups: int = Field(ge=0)
    low_similarity_groups: int = Field(ge=0)
    unavailable_similarity_groups: int = Field(ge=0)
    number_mismatch_count: int = Field(ge=0)
    date_mismatch_count: int = Field(ge=0)
    measurement_mismatch_count: int = Field(ge=0)
    reference_mismatch_count: int = Field(ge=0)
    negation_mismatch_count: int = Field(ge=0)
    warnings: list[str] | list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    requested_by: SimilarityRequesterReference | None = None
    created_at: datetime


class SimilarityRunListResponse(PaginationData[SimilarityRunResponse]):
    pass


class SimilaritySummaryResponse(ApiSchema):
    run_id: UUID
    status: SimilarityRunStatus
    average_similarity: float | None = Field(default=None, ge=0, le=1)
    minimum_similarity: float | None = Field(default=None, ge=0, le=1)
    maximum_similarity: float | None = Field(default=None, ge=0, le=1)
    translation_group_count: int = Field(ge=0)
    eligible_group_count: int = Field(ge=0)
    analysed_group_count: int = Field(ge=0)
    skipped_group_count: int = Field(ge=0)
    failed_group_count: int = Field(ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    pair_averages: dict[str, float | None] = Field(default_factory=dict)
    mismatches: dict[str, int] = Field(default_factory=dict)
    section_count: int = Field(ge=0)
    finding_count: int = Field(default=0, ge=0)
    warnings: list[str] | list[dict[str, Any]] = Field(default_factory=list)


class TranslationSimilarityResultResponse(ApiSchema):
    id: UUID
    similarity_run_id: UUID
    translation_group_id: UUID
    detected_section_id: UUID | None = None
    container_id: UUID | None = None
    source_reference: str
    source_language_code: str
    target_language_code: str
    source_member_id: UUID | None = None
    target_member_id: UUID | None = None
    source_text_hash: str
    target_text_hash: str
    source_text_snippet: str | None = None
    target_text_snippet: str | None = None
    similarity_score: float | None = Field(default=None, ge=0, le=1)
    similarity_category: SimilarityCategory
    confidence: float = Field(ge=0, le=1)
    structural_group_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    analysis_status: SimilarityAnalysisStatus
    source_character_count: int = Field(ge=0)
    target_character_count: int = Field(ge=0)
    length_ratio: float | None = Field(default=None, ge=0)
    number_consistency_status: ConsistencyStatus
    date_consistency_status: ConsistencyStatus
    measurement_consistency_status: ConsistencyStatus
    reference_consistency_status: ConsistencyStatus
    negation_consistency_status: ConsistencyStatus
    number_details: dict[str, Any] = Field(default_factory=dict)
    date_details: dict[str, Any] = Field(default_factory=dict)
    measurement_details: dict[str, Any] = Field(default_factory=dict)
    reference_details: dict[str, Any] = Field(default_factory=dict)
    negation_details: dict[str, Any] = Field(default_factory=dict)
    chunk_count_source: int = Field(ge=0)
    chunk_count_target: int = Field(ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] | list[dict[str, Any]] = Field(default_factory=list)
    finding_count: int = Field(default=0, ge=0)
    related_finding_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class TranslationSimilarityResultListResponse(
    PaginationData[TranslationSimilarityResultResponse]
):
    pass


class SectionSimilaritySummaryResponse(ApiSchema):
    id: UUID
    similarity_run_id: UUID
    detected_section_id: UUID | None = None
    canonical_section_code: str
    total_groups: int = Field(ge=0)
    eligible_groups: int = Field(ge=0)
    analysed_groups: int = Field(ge=0)
    average_similarity: float | None = Field(default=None, ge=0, le=1)
    minimum_similarity: float | None = Field(default=None, ge=0, le=1)
    low_similarity_groups: int = Field(ge=0)
    number_mismatches: int = Field(ge=0)
    date_mismatches: int = Field(ge=0)
    measurement_mismatches: int = Field(ge=0)
    reference_mismatches: int = Field(ge=0)
    negation_mismatches: int = Field(ge=0)
    pairwise_summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SectionSimilaritySummaryListResponse(
    PaginationData[SectionSimilaritySummaryResponse]
):
    pass
