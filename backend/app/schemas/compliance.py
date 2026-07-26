"""Public Phase 8 compliance job, run, summary, and comparison schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.compliance_enums import (
    ComplianceJobStatus,
    ComplianceJobType,
    ComplianceRunStatus,
    ComplianceStatus,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


def _required_reason(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Reason must not be empty.")
    return normalized


class ComplianceStartRequest(ApiSchema):
    document_file_id: UUID
    extraction_run_id: UUID | None = None
    ocr_run_id: UUID | None = None
    language_detection_run_id: UUID | None = None
    validation_rule_id: UUID | None = None
    force: bool = False


class ComplianceQueuedResponse(ApiSchema):
    job_id: UUID
    status: ComplianceJobStatus
    progress: int = Field(ge=0, le=100)
    document_file_id: UUID
    run_id: UUID | None = None
    reused_existing_result: bool = False


class ComplianceRevalidateRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=2000)
    validation_rule_id: UUID | None = None

    _reason = field_validator("reason", mode="before")(_required_reason)


class ComplianceDocumentReference(ApiSchema):
    id: UUID
    base_document_code: str
    title: str
    department_id: UUID
    department_name: str | None = None


class ComplianceRevisionReference(ApiSchema):
    id: UUID
    revision_code: str
    full_document_code: str


class ComplianceFileReference(ApiSchema):
    id: UUID
    filename: str
    file_extension: str


class ComplianceRuleReference(ApiSchema):
    id: UUID
    code: str
    name: str
    version: int | None = None


class ComplianceRequesterReference(ApiSchema):
    id: UUID
    name: str


class ComplianceJobResponse(ApiSchema):
    id: UUID
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    extraction_run_id: UUID
    ocr_run_id: UUID | None
    language_detection_run_id: UUID
    validation_rule_id: UUID
    document: ComplianceDocumentReference | None = None
    revision: ComplianceRevisionReference | None = None
    file: ComplianceFileReference | None = None
    validation_rule: ComplianceRuleReference | None = None
    job_type: ComplianceJobType
    status: ComplianceJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None
    source_content_hash: str | None = None
    requested_by: ComplianceRequesterReference | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any] | None = None
    result_summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ComplianceCancelResponse(ApiSchema):
    id: UUID
    status: ComplianceJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    cancelled_at: datetime | None = None


class ComplianceJobListResponse(PaginationData[ComplianceJobResponse]):
    pass


class ComplianceJobFilter(ApiSchema):
    search: str | None = None
    department_id: UUID | None = None
    document_id: UUID | None = None
    document_file_id: UUID | None = None
    validation_rule_id: UUID | None = None
    compliance_status: ComplianceStatus | None = None
    requested_by: UUID | None = None
    status: ComplianceJobStatus | None = None
    requested_from: datetime | None = None
    requested_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "requestedAt"
    sort_order: str = "desc"


class ComplianceRunResponse(ApiSchema):
    id: UUID
    compliance_job_id: UUID
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    extraction_run_id: UUID
    ocr_run_id: UUID | None
    language_detection_run_id: UUID
    validation_rule_id: UUID
    document: ComplianceDocumentReference | None = None
    revision: ComplianceRevisionReference | None = None
    file: ComplianceFileReference | None = None
    validation_rule: ComplianceRuleReference | None = None
    rule_snapshot: dict[str, Any]
    source_content_hash: str
    status: ComplianceRunStatus
    compliance_status: ComplianceStatus
    compliance_score: float = Field(ge=0, le=100)
    maximum_score: float = Field(ge=0, le=100)
    document_code_score: float = Field(ge=0)
    language_presence_score: float = Field(ge=0)
    language_coverage_score: float = Field(ge=0)
    section_completeness_score: float = Field(ge=0)
    language_order_score: float = Field(ge=0)
    translation_group_score: float = Field(ge=0)
    table_completeness_score: float = Field(ge=0)
    total_findings: int = Field(ge=0)
    critical_findings: int = Field(ge=0)
    major_findings: int = Field(ge=0)
    minor_findings: int = Field(ge=0)
    information_findings: int = Field(ge=0)
    open_findings: int = Field(ge=0)
    required_languages: list[str]
    detected_languages: list[str] | dict[str, Any]
    missing_languages: list[str]
    required_sections: list[str]
    detected_sections: list[str] | dict[str, Any]
    missing_sections: list[str]
    warnings: list[str] | list[dict[str, Any]]
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    requested_by: ComplianceRequesterReference | None
    created_at: datetime


class ComplianceRunListResponse(PaginationData[ComplianceRunResponse]):
    pass


class ComplianceLanguageSummary(ApiSchema):
    presence: dict[str, str] = Field(default_factory=dict)
    block_coverage: dict[str, float] = Field(default_factory=dict)
    character_coverage: dict[str, float] = Field(default_factory=dict)
    average_confidence: dict[str, float | None] = Field(default_factory=dict)


class LanguageComplianceMetric(ApiSchema):
    language_code: str
    presence: str
    block_coverage: float = Field(ge=0, le=100)
    character_coverage: float = Field(ge=0, le=100)
    minimum_block_coverage: float | None = Field(default=None, ge=0, le=100)
    minimum_character_coverage: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    finding_count: int = Field(default=0, ge=0)


class ComplianceTranslationGroupSummary(ApiSchema):
    total: int = Field(default=0, ge=0)
    complete: int = Field(default=0, ge=0)
    incomplete: int = Field(default=0, ge=0)
    order_invalid: int = Field(default=0, ge=0)
    low_confidence: int = Field(default=0, ge=0)


class ComplianceFindingSummary(ApiSchema):
    total: int = Field(default=0, ge=0)
    open: int = Field(default=0, ge=0)
    critical: int = Field(default=0, ge=0)
    major: int = Field(default=0, ge=0)
    minor: int = Field(default=0, ge=0)
    information: int = Field(default=0, ge=0)


class ComplianceSummaryResponse(ApiSchema):
    run_id: UUID
    status: ComplianceRunStatus
    compliance_status: ComplianceStatus
    compliance_score: float = Field(ge=0, le=100)
    required_languages: list[str]
    language_presence: dict[str, str] = Field(default_factory=dict)
    language_coverage: dict[str, float] = Field(default_factory=dict)
    language: ComplianceLanguageSummary | None = None
    language_metrics: list[LanguageComplianceMetric] = Field(
        default_factory=list
    )
    required_sections: int = Field(ge=0)
    detected_sections: int = Field(ge=0)
    complete_sections: int = Field(ge=0)
    translation_groups: ComplianceTranslationGroupSummary
    findings: ComplianceFindingSummary
    warnings: list[str] | list[dict[str, Any]] = Field(default_factory=list)


class ComplianceScoreComponent(ApiSchema):
    earned: float = Field(ge=0)
    maximum: float = Field(ge=0)


class ComplianceScorePenalties(ApiSchema):
    major: float = Field(default=0, le=0)
    minor: float = Field(default=0, le=0)
    other: float = Field(default=0, le=0)


class ComplianceScoreBreakdownResponse(ApiSchema):
    document_code: ComplianceScoreComponent
    language_presence: ComplianceScoreComponent
    language_coverage: ComplianceScoreComponent
    section_completeness: ComplianceScoreComponent
    language_order: ComplianceScoreComponent
    translation_groups: ComplianceScoreComponent
    table_completeness: ComplianceScoreComponent
    penalties: ComplianceScorePenalties
    weighted_score: float = Field(ge=0, le=100)
    score_cap: float | None = Field(default=None, ge=0, le=100)
    final_score: float = Field(ge=0, le=100)


class ComplianceComparisonResponse(ApiSchema):
    current_run_id: UUID
    previous_run_id: UUID
    score_change: float
    previous_status: ComplianceStatus
    current_status: ComplianceStatus
    languages_added: list[str] = Field(default_factory=list)
    languages_removed: list[str] = Field(default_factory=list)
    sections_added: list[str] = Field(default_factory=list)
    sections_removed: list[str] = Field(default_factory=list)
    new_findings: int = Field(default=0, ge=0)
    resolved_candidates: int = Field(default=0, ge=0)
    repeated_findings: int = Field(default=0, ge=0)
    translation_group_completeness_change: float | None = None
