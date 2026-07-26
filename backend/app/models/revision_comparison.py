"""Retained Phase 9 revision-comparison summaries."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.revision_comparison_job import revision_enum_values


class RevisionComparisonStatus(StrEnum):
    """Official retained result status."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class RevisionComparisonClassification(StrEnum):
    """Overall direction without mutating either revision."""

    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    UNCHANGED = "UNCHANGED"
    MIXED = "MIXED"


class RevisionComparison(Base):
    """Immutable summary for a completed comparison job."""

    __tablename__ = "revision_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "revision_comparison_job_id",
            name="uq_revision_comparisons_job_id",
        ),
        CheckConstraint(
            "base_revision_id <> target_revision_id",
            name="revision_comparisons_distinct_revisions",
        ),
        CheckConstraint(
            "total_changes >= 0 AND added_blocks >= 0 "
            "AND removed_blocks >= 0 AND modified_blocks >= 0 "
            "AND moved_blocks >= 0 AND unchanged_blocks >= 0 "
            "AND added_sections >= 0 AND removed_sections >= 0 "
            "AND modified_sections >= 0 "
            "AND added_translation_groups >= 0 "
            "AND removed_translation_groups >= 0 "
            "AND modified_translation_groups >= 0 "
            "AND new_findings >= 0 AND removed_findings >= 0 "
            "AND repeated_findings >= 0 AND severity_change_count >= 0",
            name="revision_comparisons_counts_nonnegative",
        ),
        CheckConstraint(
            "(base_content_hash IS NULL OR length(base_content_hash) = 64) "
            "AND (target_content_hash IS NULL "
            "OR length(target_content_hash) = 64)",
            name="revision_comparisons_hash_lengths",
        ),
        Index("ix_revision_comparisons_document_id", "document_id"),
        Index(
            "ix_revision_comparisons_base_revision_id", "base_revision_id"
        ),
        Index(
            "ix_revision_comparisons_target_revision_id",
            "target_revision_id",
        ),
        Index("ix_revision_comparisons_status", "status"),
        Index("ix_revision_comparisons_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    revision_comparison_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("revision_comparison_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_revision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_revision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_document_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_document_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_extraction_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_extraction_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    base_compliance_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_compliance_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    base_similarity_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_similarity_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    base_glossary_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_validation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_glossary_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_validation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[RevisionComparisonStatus] = mapped_column(
        Enum(
            RevisionComparisonStatus,
            name="revision_comparison_status",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    classification: Mapped[RevisionComparisonClassification] = mapped_column(
        Enum(
            RevisionComparisonClassification,
            name="revision_comparison_classification",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RevisionComparisonClassification.UNCHANGED,
        server_default=RevisionComparisonClassification.UNCHANGED.value,
    )
    base_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    target_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    total_changes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    added_blocks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    removed_blocks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    modified_blocks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    moved_blocks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    unchanged_blocks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    added_sections: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    removed_sections: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    modified_sections: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    added_translation_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    removed_translation_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    modified_translation_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    language_coverage_change_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    compliance_score_change: Mapped[float | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )
    similarity_score_change: Mapped[float | None] = mapped_column(
        Numeric(8, 5), nullable=True
    )
    new_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    removed_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    repeated_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    severity_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    warnings_json: Mapped[list[dict[str, Any] | str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
