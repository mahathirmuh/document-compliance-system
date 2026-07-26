"""Public Phase 9 revision-comparison contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.revision_change import (
    RevisionChangeType,
    RevisionEntityType,
)
from app.models.revision_comparison import (
    RevisionComparisonClassification,
    RevisionComparisonStatus,
)
from app.models.revision_comparison_job import (
    RevisionComparisonJobStatus,
    RevisionComparisonJobType,
)
from app.schemas.base import ApiSchema


class RevisionComparisonStartRequest(ApiSchema):
    document_id: UUID
    base_revision_id: UUID
    target_revision_id: UUID
    force: bool = False

    @model_validator(mode="after")
    def distinct_revisions(self) -> RevisionComparisonStartRequest:
        if self.base_revision_id == self.target_revision_id:
            raise ValueError("Base and target revisions must be different.")
        return self


class RevisionComparisonQueuedResponse(ApiSchema):
    job_id: UUID
    status: RevisionComparisonJobStatus
    progress: int = Field(ge=0, le=100)
    comparison_id: UUID | None = None
    reused_existing_result: bool = False


class RevisionComparisonJobResponse(ApiSchema):
    id: UUID
    document_id: UUID
    base_revision_id: UUID
    target_revision_id: UUID
    base_document_file_id: UUID
    target_document_file_id: UUID
    job_type: RevisionComparisonJobType
    status: RevisionComparisonJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None
    requested_by: UUID | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    error_message: str | None
    result_summary: dict[str, object] | None = None


class RevisionComparisonJobListResponse(ApiSchema):
    items: list[RevisionComparisonJobResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class RevisionComparisonResponse(ApiSchema):
    id: UUID
    revision_comparison_job_id: UUID
    document_id: UUID
    base_revision_id: UUID
    target_revision_id: UUID
    base_document_file_id: UUID
    target_document_file_id: UUID
    base_extraction_run_id: UUID | None
    target_extraction_run_id: UUID | None
    base_compliance_run_id: UUID | None
    target_compliance_run_id: UUID | None
    base_similarity_run_id: UUID | None
    target_similarity_run_id: UUID | None
    base_glossary_run_id: UUID | None
    target_glossary_run_id: UUID | None
    status: RevisionComparisonStatus
    classification: RevisionComparisonClassification
    base_content_hash: str | None
    target_content_hash: str | None
    total_changes: int
    added_blocks: int
    removed_blocks: int
    modified_blocks: int
    moved_blocks: int
    unchanged_blocks: int
    added_sections: int
    removed_sections: int
    modified_sections: int
    added_translation_groups: int
    removed_translation_groups: int
    modified_translation_groups: int
    compliance_score_change: float | None
    similarity_score_change: float | None
    new_findings: int
    removed_findings: int
    repeated_findings: int
    severity_change_count: int
    language_coverage_change: dict[str, object]
    summary: dict[str, object]
    warnings: list[object]
    requested_by: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RevisionComparisonSummaryResponse(ApiSchema):
    comparison_id: UUID
    classification: RevisionComparisonClassification
    total_changes: int
    added: int
    removed: int
    modified: int
    moved: int
    unchanged: int
    compliance_score_change: float | None
    similarity_score_change: float | None
    new_findings: int
    no_longer_reproduced: int
    summary: dict[str, object]
    warnings: list[object]


class RevisionChangeResponse(ApiSchema):
    id: UUID
    revision_comparison_id: UUID
    change_type: RevisionChangeType
    entity_type: RevisionEntityType
    base_container_id: UUID | None
    target_container_id: UUID | None
    base_section_id: UUID | None
    target_section_id: UUID | None
    base_translation_group_id: UUID | None
    target_translation_group_id: UUID | None
    base_block_id: UUID | None
    target_block_id: UUID | None
    language_code: str | None
    source_reference_base: str | None
    source_reference_target: str | None
    base_text_snapshot: str | None
    target_text_snapshot: str | None
    text_similarity: float | None
    structural_similarity: float | None
    alignment_confidence: float | None
    character_change_count: int
    word_change_count: int
    metadata: dict[str, object]
    created_at: datetime


class RevisionChangeListResponse(ApiSchema):
    items: list[RevisionChangeResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class RevisionSectionChange(ApiSchema):
    section_key: str
    added: int
    removed: int
    modified: int
    moved: int
    unchanged: int


class RevisionSectionChangesResponse(ApiSchema):
    comparison_id: UUID
    items: list[RevisionSectionChange]


class RevisionLanguageChange(ApiSchema):
    language_code: Literal["id", "en", "zh", "unknown"]
    base_count: int
    target_count: int
    base_coverage: float | None = Field(default=None, ge=0, le=100)
    target_coverage: float | None = Field(default=None, ge=0, le=100)
    coverage_change: float | None = Field(default=None, ge=-100, le=100)
    additions: int
    removals: int
    modifications: int
    base_presence: bool
    target_presence: bool
    regression: bool
    fixed_missing_language: bool


class RevisionLanguageChangesResponse(ApiSchema):
    comparison_id: UUID
    items: list[RevisionLanguageChange]
    groups_added: int = 0
    groups_removed: int = 0
    groups_modified: int = 0


class RevisionFindingChange(ApiSchema):
    finding_key: str
    finding_code: str
    comparison_status: Literal[
        "NEW",
        "NO_LONGER_REPRODUCED",
        "REPEATED",
        "SEVERITY_INCREASED",
        "SEVERITY_DECREASED",
        "STATUS_CHANGED",
        "UNCHANGED",
    ]
    base_severity: str | None
    target_severity: str | None
    base_status: str | None
    target_status: str | None
    section: str | None = None
    language: str | None = None
    location: str | None = None
    candidate_resolution: bool = False


class RevisionFindingChangesResponse(ApiSchema):
    comparison_id: UUID
    items: list[RevisionFindingChange]
    summary: dict[str, int]


class RevisionComparisonHistoryResponse(ApiSchema):
    items: list[RevisionComparisonResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
