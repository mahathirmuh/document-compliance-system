"""Queued Phase 8 compliance-validation work."""

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
from app.models.compliance_enums import (
    ACTIVE_COMPLIANCE_JOB_STATUSES,
    ComplianceJobStatus,
    ComplianceJobType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.language_detection_run import LanguageDetectionRun
    from app.models.ocr_run import OCRRun
    from app.models.user import User
    from app.models.validation_rule import ValidationRule

_ACTIVE_STATUS_SQL = ", ".join(
    f"'{status.value}'" for status in ACTIVE_COMPLIANCE_JOB_STATUSES
)


class ComplianceJob(Base):
    """One asynchronous request over a resolved source-content version."""

    __tablename__ = "compliance_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="compliance_jobs_progress_range",
        ),
        CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= 1 "
            "AND attempt_number <= maximum_attempts",
            name="compliance_jobs_attempt_range",
        ),
        CheckConstraint(
            "source_content_hash IS NULL "
            "OR length(source_content_hash) = 64",
            name="compliance_jobs_source_hash_length",
        ),
        Index("ix_compliance_jobs_document_id", "document_id"),
        Index(
            "ix_compliance_jobs_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_compliance_jobs_document_file_id", "document_file_id"),
        Index("ix_compliance_jobs_extraction_run_id", "extraction_run_id"),
        Index("ix_compliance_jobs_ocr_run_id", "ocr_run_id"),
        Index(
            "ix_compliance_jobs_language_detection_run_id",
            "language_detection_run_id",
        ),
        Index("ix_compliance_jobs_validation_rule_id", "validation_rule_id"),
        Index("ix_compliance_jobs_status", "status"),
        Index("ix_compliance_jobs_requested_by", "requested_by"),
        Index("ix_compliance_jobs_requested_at", "requested_at"),
        Index("ix_compliance_jobs_source_content_hash", "source_content_hash"),
        Index(
            "uq_compliance_jobs_active_source",
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
    extraction_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ocr_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_detection_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_type: Mapped[ComplianceJobType] = mapped_column(
        Enum(
            ComplianceJobType,
            name="compliance_job_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ComplianceJobType.INITIAL_VALIDATION,
        server_default=ComplianceJobType.INITIAL_VALIDATION.value,
    )
    status: Mapped[ComplianceJobStatus] = mapped_column(
        Enum(
            ComplianceJobStatus,
            name="compliance_job_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ComplianceJobStatus.QUEUED,
        server_default=ComplianceJobStatus.QUEUED.value,
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
    source_content_hash: Mapped[str | None] = mapped_column(
        String(64),
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
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    maximum_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
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

    document: Mapped[Document] = relationship(foreign_keys=[document_id])
    revision: Mapped[DocumentRevision] = relationship(
        foreign_keys=[document_revision_id]
    )
    document_file: Mapped[DocumentFile] = relationship(
        back_populates="compliance_jobs",
        foreign_keys=[document_file_id],
    )
    extraction_run: Mapped[ExtractionRun] = relationship(
        foreign_keys=[extraction_run_id]
    )
    ocr_run: Mapped[OCRRun | None] = relationship(foreign_keys=[ocr_run_id])
    language_detection_run: Mapped[LanguageDetectionRun] = relationship(
        foreign_keys=[language_detection_run_id]
    )
    validation_rule: Mapped[ValidationRule] = relationship(
        foreign_keys=[validation_rule_id]
    )
    requester: Mapped[User | None] = relationship(
        foreign_keys=[requested_by]
    )
    compliance_run: Mapped[ComplianceRun | None] = relationship(
        back_populates="compliance_job",
        uselist=False,
        passive_deletes=True,
    )

    @validates("source_content_hash")
    def normalize_source_hash(self, _: str, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError(
                "source_content_hash must be 64 lowercase hex digits."
            )
        return normalized
