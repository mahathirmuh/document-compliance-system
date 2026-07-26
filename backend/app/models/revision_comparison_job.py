"""Queued Phase 9 revision-comparison work."""

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
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RevisionComparisonJobType(StrEnum):
    """Why a retained comparison was requested."""

    INITIAL = "INITIAL"
    REANALYSIS = "REANALYSIS"
    MANUAL = "MANUAL"


class RevisionComparisonJobStatus(StrEnum):
    """Durable worker stages visible to API clients."""

    QUEUED = "QUEUED"
    LOADING_REVISIONS = "LOADING_REVISIONS"
    ALIGNING_SECTIONS = "ALIGNING_SECTIONS"
    ALIGNING_GROUPS = "ALIGNING_GROUPS"
    COMPARING_CONTENT = "COMPARING_CONTENT"
    COMPARING_LANGUAGES = "COMPARING_LANGUAGES"
    COMPARING_FINDINGS = "COMPARING_FINDINGS"
    CALCULATING_SUMMARY = "CALCULATING_SUMMARY"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_REVISION_COMPARISON_JOB_STATUSES = frozenset(
    {
        RevisionComparisonJobStatus.QUEUED,
        RevisionComparisonJobStatus.LOADING_REVISIONS,
        RevisionComparisonJobStatus.ALIGNING_SECTIONS,
        RevisionComparisonJobStatus.ALIGNING_GROUPS,
        RevisionComparisonJobStatus.COMPARING_CONTENT,
        RevisionComparisonJobStatus.COMPARING_LANGUAGES,
        RevisionComparisonJobStatus.COMPARING_FINDINGS,
        RevisionComparisonJobStatus.CALCULATING_SUMMARY,
        RevisionComparisonJobStatus.PERSISTING,
        RevisionComparisonJobStatus.CANCEL_REQUESTED,
    }
)
TERMINAL_REVISION_COMPARISON_JOB_STATUSES = frozenset(
    {
        RevisionComparisonJobStatus.COMPLETED,
        RevisionComparisonJobStatus.PARTIALLY_COMPLETED,
        RevisionComparisonJobStatus.FAILED,
        RevisionComparisonJobStatus.CANCELLED,
    }
)


def revision_enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


_ACTIVE_STATUS_SQL = ", ".join(
    f"'{status.value}'" for status in ACTIVE_REVISION_COMPARISON_JOB_STATUSES
)


class RevisionComparisonJob(Base):
    """One asynchronous comparison between two revisions of one document."""

    __tablename__ = "revision_comparison_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="revision_comparison_jobs_progress_range",
        ),
        CheckConstraint(
            "base_revision_id <> target_revision_id",
            name="revision_comparison_jobs_distinct_revisions",
        ),
        CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= attempt_number",
            name="revision_comparison_jobs_attempt_range",
        ),
        Index("ix_revision_comparison_jobs_document_id", "document_id"),
        Index(
            "ix_revision_comparison_jobs_base_revision_id",
            "base_revision_id",
        ),
        Index(
            "ix_revision_comparison_jobs_target_revision_id",
            "target_revision_id",
        ),
        Index("ix_revision_comparison_jobs_status", "status"),
        Index(
            "ix_revision_comparison_jobs_requested_at",
            "requested_at",
        ),
        Index(
            "uq_revision_comparison_jobs_active_pair",
            "document_id",
            "base_revision_id",
            "target_revision_id",
            unique=True,
            postgresql_where=text(f"status IN ({_ACTIVE_STATUS_SQL})"),
            sqlite_where=text(f"status IN ({_ACTIVE_STATUS_SQL})"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
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
    job_type: Mapped[RevisionComparisonJobType] = mapped_column(
        Enum(
            RevisionComparisonJobType,
            name="revision_comparison_job_type",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RevisionComparisonJobType.INITIAL,
        server_default=RevisionComparisonJobType.INITIAL.value,
    )
    status: Mapped[RevisionComparisonJobStatus] = mapped_column(
        Enum(
            RevisionComparisonJobStatus,
            name="revision_comparison_job_status",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RevisionComparisonJobStatus.QUEUED,
        server_default=RevisionComparisonJobStatus.QUEUED.value,
    )
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    maximum_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
