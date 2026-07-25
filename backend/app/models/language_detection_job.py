"""Durable background jobs for Phase 7 language detection."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.language_detection_run import LanguageDetectionRun
    from app.models.user import User


class LanguageDetectionJobType(StrEnum):
    """Why a language detection job was created."""

    INITIAL_DETECTION = "INITIAL_DETECTION"
    RE_DETECTION = "RE_DETECTION"


class LanguageDetectionJobStatus(StrEnum):
    """Application-owned job lifecycle, independent from Celery state."""

    QUEUED = "QUEUED"
    LOADING_CONTENT = "LOADING_CONTENT"
    DETECTING = "DETECTING"
    AGGREGATING = "AGGREGATING"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES: frozenset[
    LanguageDetectionJobStatus
] = frozenset(
    {
        LanguageDetectionJobStatus.QUEUED,
        LanguageDetectionJobStatus.LOADING_CONTENT,
        LanguageDetectionJobStatus.DETECTING,
        LanguageDetectionJobStatus.AGGREGATING,
        LanguageDetectionJobStatus.PERSISTING,
        LanguageDetectionJobStatus.CANCEL_REQUESTED,
    }
)


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class LanguageDetectionJob(Base):
    """One queued language-analysis request and its client-safe state."""

    __tablename__ = "language_detection_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="progress_range",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="attempt_number_positive",
        ),
        CheckConstraint(
            "maximum_attempts >= 1",
            name="maximum_attempts_positive",
        ),
        CheckConstraint(
            "attempt_number <= maximum_attempts",
            name="attempt_within_maximum",
        ),
        CheckConstraint(
            "source_content_hash IS NULL "
            "OR length(source_content_hash) = 64",
            name="source_content_hash_length",
        ),
        Index("ix_language_detection_jobs_document_id", "document_id"),
        Index(
            "ix_language_detection_jobs_document_revision_id",
            "document_revision_id",
        ),
        Index(
            "ix_language_detection_jobs_document_file_id",
            "document_file_id",
        ),
        Index(
            "ix_language_detection_jobs_extraction_run_id",
            "extraction_run_id",
        ),
        Index("ix_language_detection_jobs_ocr_run_id", "ocr_run_id"),
        Index("ix_language_detection_jobs_status", "status"),
        Index(
            "ix_language_detection_jobs_requested_by",
            "requested_by",
        ),
        Index(
            "ix_language_detection_jobs_requested_at",
            "requested_at",
        ),
        Index(
            "ix_language_detection_jobs_source_content_hash",
            "source_content_hash",
        ),
        Index(
            "uq_language_detection_jobs_one_active_per_file",
            "document_file_id",
            unique=True,
            postgresql_where=text(
                "status IN ('QUEUED', 'LOADING_CONTENT', 'DETECTING', "
                "'AGGREGATING', 'PERSISTING', 'CANCEL_REQUESTED')"
            ),
            sqlite_where=text(
                "status IN ('QUEUED', 'LOADING_CONTENT', 'DETECTING', "
                "'AGGREGATING', 'PERSISTING', 'CANCEL_REQUESTED')"
            ),
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
    job_type: Mapped[LanguageDetectionJobType] = mapped_column(
        Enum(
            LanguageDetectionJobType,
            name="language_detection_job_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=LanguageDetectionJobType.INITIAL_DETECTION,
        server_default=LanguageDetectionJobType.INITIAL_DETECTION.value,
    )
    status: Mapped[LanguageDetectionJobStatus] = mapped_column(
        Enum(
            LanguageDetectionJobStatus,
            name="language_detection_job_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=LanguageDetectionJobStatus.QUEUED,
        server_default=LanguageDetectionJobStatus.QUEUED.value,
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
    force: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        default=3,
        server_default="3",
    )
    worker_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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
        foreign_keys=[document_file_id]
    )
    extraction_run: Mapped[ExtractionRun] = relationship(
        foreign_keys=[extraction_run_id]
    )
    requester: Mapped[User | None] = relationship(
        foreign_keys=[requested_by]
    )
    detection_run: Mapped[LanguageDetectionRun | None] = relationship(
        back_populates="job",
        uselist=False,
        foreign_keys="LanguageDetectionRun.job_id",
    )

    @validates("progress")
    def validate_progress(self, _: str, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError(
                "Language detection progress must be between 0 and 100."
            )
        return value

    @validates("source_content_hash")
    def normalize_hash(self, _: str, value: str | None) -> str | None:
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
