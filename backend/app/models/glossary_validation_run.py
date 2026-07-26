"""Durable glossary validation job and retained result."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
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
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.glossary_enums import (
    ACTIVE_GLOSSARY_VALIDATION_STATUSES,
    GlossaryValidationJobType,
    GlossaryValidationStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.glossary_match import GlossaryMatch

_ACTIVE_STATUS_SQL = ", ".join(
    f"'{status.value}'" for status in ACTIVE_GLOSSARY_VALIDATION_STATUSES
)


class GlossaryValidationRun(Base):
    """One asynchronous lifecycle; completed rows are immutable history."""

    __tablename__ = "glossary_validation_runs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="glossary_validation_runs_progress_range",
        ),
        CheckConstraint(
            "length(source_content_hash) = 64",
            name="glossary_validation_runs_source_hash_length",
        ),
        CheckConstraint(
            "total_terms >= 0 AND matched_terms >= 0 "
            "AND preferred_term_matches >= 0 "
            "AND forbidden_term_matches >= 0 "
            "AND missing_required_translations >= 0 "
            "AND inconsistent_terms >= 0 "
            "AND exception_applied_count >= 0 AND total_findings >= 0",
            name="glossary_validation_runs_counts_nonnegative",
        ),
        Index("ix_glossary_runs_document_id", "document_id"),
        Index(
            "ix_glossary_runs_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_glossary_runs_document_file_id", "document_file_id"),
        Index("ix_glossary_runs_compliance_run_id", "compliance_run_id"),
        Index(
            "ix_glossary_runs_language_detection_run_id",
            "language_detection_run_id",
        ),
        Index("ix_glossary_runs_status", "status"),
        Index("ix_glossary_runs_requested_by", "requested_by"),
        Index("ix_glossary_runs_created_at", "created_at"),
        Index("ix_glossary_runs_source_content_hash", "source_content_hash"),
        Index(
            "uq_glossary_runs_active_source",
            "document_file_id",
            "source_content_hash",
            unique=True,
            postgresql_where=text(f"status IN ({_ACTIVE_STATUS_SQL})"),
            sqlite_where=text(f"status IN ({_ACTIVE_STATUS_SQL})"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_revision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    compliance_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_detection_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    glossary_profile_ids_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    profile_snapshots_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    job_type: Mapped[GlossaryValidationJobType] = mapped_column(
        Enum(
            GlossaryValidationJobType,
            name="glossary_validation_job_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GlossaryValidationJobType.INITIAL,
        server_default=GlossaryValidationJobType.INITIAL.value,
    )
    status: Mapped[GlossaryValidationStatus] = mapped_column(
        Enum(
            GlossaryValidationStatus,
            name="glossary_validation_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GlossaryValidationStatus.QUEUED,
        server_default=GlossaryValidationStatus.QUEUED.value,
    )
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    source_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    total_terms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    matched_terms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    preferred_term_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    forbidden_term_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    missing_required_translations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    inconsistent_terms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    exception_applied_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_findings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    warnings_json: Mapped[list[str] | list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    matches: Mapped[list[GlossaryMatch]] = relationship(
        back_populates="validation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GlossaryMatch.created_at",
    )

    @validates("source_content_hash")
    def normalize_source_hash(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError(
                "source_content_hash must be 64 lowercase hex digits."
            )
        return normalized
