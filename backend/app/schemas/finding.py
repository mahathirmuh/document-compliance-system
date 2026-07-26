"""Public Phase 8 finding requests, filters, and response schemas."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.compliance import (
    ComplianceDocumentReference,
    ComplianceRevisionReference,
    ComplianceRuleReference,
)
from app.schemas.document_revision import UserReference

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_required_text(value: str) -> str:
    """Trim user text and reject hidden control characters."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be empty.")
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("Value contains unsupported control characters.")
    return normalized


def sanitize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("Value contains unsupported control characters.")
    return normalized


class FindingCreateManualRequest(ApiSchema):
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    severity: FindingSeverity
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10_000)
    recommendation: str | None = Field(default=None, max_length=5000)
    source_reference: str | None = Field(default=None, max_length=1000)
    page_number: int | None = Field(default=None, ge=1)
    worksheet_name: str | None = Field(default=None, max_length=255)
    cell_coordinate: str | None = Field(default=None, max_length=50)
    language_code: str | None = Field(default=None, max_length=20)
    location: dict[str, Any] = Field(default_factory=dict)

    _title = field_validator("title", mode="before")(sanitize_required_text)
    _description = field_validator("description", mode="before")(sanitize_required_text)
    _optional_text = field_validator(
        "recommendation",
        "source_reference",
        "worksheet_name",
        "cell_coordinate",
        "language_code",
        mode="before",
    )(sanitize_optional_text)


class FindingUpdateRequest(ApiSchema):
    severity: FindingSeverity | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=10_000,
    )
    recommendation: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "description", mode="before")
    @classmethod
    def required_when_present(cls, value: object) -> object:
        return sanitize_required_text(value) if isinstance(value, str) else value

    _recommendation = field_validator("recommendation", mode="before")(
        sanitize_optional_text
    )


class FindingReviewRequest(ApiSchema):
    comment: str = Field(min_length=1, max_length=5000)

    _comment = field_validator("comment", mode="before")(sanitize_required_text)


class FindingResolveRequest(ApiSchema):
    comment: str = Field(min_length=1, max_length=5000)

    _comment = field_validator("comment", mode="before")(sanitize_required_text)


class FindingReopenRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=5000)

    _reason = field_validator("reason", mode="before")(sanitize_required_text)


class FindingFalsePositiveRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=5000)

    _reason = field_validator("reason", mode="before")(sanitize_required_text)


class FindingAcceptRiskRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=5000)
    expiry_date: date

    _reason = field_validator("reason", mode="before")(sanitize_required_text)


class FindingAssignRequest(ApiSchema):
    assigned_to: UUID


class FindingBulkActionBase(ApiSchema):
    finding_ids: list[UUID] = Field(min_length=1, max_length=10_000)

    @field_validator("finding_ids")
    @classmethod
    def deduplicate_finding_ids(cls, value: list[UUID]) -> list[UUID]:
        """Preserve caller order while preventing duplicate mutations."""

        return list(dict.fromkeys(value))


class FindingBulkAssignRequest(FindingBulkActionBase):
    action: Literal["ASSIGN"]
    assigned_to: UUID


class FindingBulkReviewRequest(FindingBulkActionBase):
    action: Literal["REVIEW"]
    comment: str = Field(min_length=1, max_length=5000)

    _comment = field_validator("comment", mode="before")(sanitize_required_text)


FindingBulkActionRequest = Annotated[
    FindingBulkAssignRequest | FindingBulkReviewRequest,
    Field(discriminator="action"),
]


class FindingBulkActionResponse(ApiSchema):
    action: Literal["ASSIGN", "REVIEW"]
    processed_count: int = Field(ge=1)
    finding_ids: list[UUID] = Field(min_length=1)


class FindingOccurrenceResponse(ApiSchema):
    id: UUID
    finding_id: UUID
    compliance_run_id: UUID
    detected_at: datetime
    source_reference: str | None
    location: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class FindingHistoryEntry(ApiSchema):
    """One bounded workflow event derived from the append-only audit log."""

    id: UUID
    action: str
    previous_status: FindingStatus | None
    new_status: FindingStatus
    comment: str | None
    reason: str | None
    actor: UserReference | None
    created_at: datetime


class FindingListItem(ApiSchema):
    id: UUID
    compliance_run_id: UUID | None
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    finding_code: FindingCode
    finding_type: FindingType
    severity: FindingSeverity
    status: FindingStatus
    document: ComplianceDocumentReference | None = None
    revision: ComplianceRevisionReference | None = None
    validation_rule: ComplianceRuleReference | None = None
    title: str
    language_code: str | None
    detected_section_id: UUID | None
    section_code: str | None = None
    source_reference: str | None
    page_number: int | None
    worksheet_name: str | None
    cell_coordinate: str | None
    assigned_to: UserReference | UUID | None
    is_system_generated: bool
    is_repeat: bool
    created_at: datetime
    updated_at: datetime


class FindingResponse(FindingListItem):
    validation_rule_id: UUID | None
    description: str
    recommendation: str | None
    container_id: UUID | None
    translation_group_id: UUID | None
    extracted_block_id: UUID | None
    ocr_block_id: UUID | None
    location: dict[str, Any] = Field(default_factory=dict)
    expected_value: dict[str, Any] | list[Any] | None
    actual_value: dict[str, Any] | list[Any] | None
    metrics: dict[str, Any] = Field(default_factory=dict)
    previous_finding_id: UUID | None
    created_by: UUID | None
    reviewed_by: UserReference | UUID | None
    reviewed_at: datetime | None
    review_comment: str | None
    resolved_by: UserReference | UUID | None
    resolved_at: datetime | None
    resolution_comment: str | None
    false_positive_by: UserReference | UUID | None
    false_positive_at: datetime | None
    false_positive_reason: str | None
    accepted_risk_by: UserReference | UUID | None
    accepted_risk_at: datetime | None
    accepted_risk_reason: str | None
    accepted_risk_expiry_date: date | None
    reopened_by: UserReference | UUID | None
    reopened_at: datetime | None
    reopen_reason: str | None
    occurrences: list[FindingOccurrenceResponse] = Field(default_factory=list)
    history: list[FindingHistoryEntry] = Field(default_factory=list)


class FindingListResponse(PaginationData[FindingListItem]):
    pass


class FindingFilter(ApiSchema):
    search: str | None = None
    department_id: UUID | None = None
    document_id: UUID | None = None
    revision_id: UUID | None = None
    compliance_run_id: UUID | None = None
    detected_section_id: UUID | None = None
    section_code: str | None = None
    finding_code: FindingCode | None = None
    finding_type: FindingType | None = None
    severity: FindingSeverity | None = None
    status: FindingStatus | None = None
    language_code: str | None = None
    assigned_to: UUID | None = None
    created_by_system: bool | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "severity"
    sort_order: str = "desc"
