"""Queued document-content extraction work."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.user import User


class ExtractionJobType(StrEnum):
    """Reason an extraction job was requested."""

    INITIAL_EXTRACTION = "INITIAL_EXTRACTION"
    RE_EXTRACTION = "RE_EXTRACTION"
    MANUAL_EXTRACTION = "MANUAL_EXTRACTION"


class ExtractionJobStatus(StrEnum):
    """Lifecycle state persisted independently from Celery state."""

    QUEUED = "QUEUED"
    INSPECTING = "INSPECTING"
    EXTRACTING = "EXTRACTING"
    NORMALISING = "NORMALISING"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    OCR_REQUIRED = "OCR_REQUIRED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_EXTRACTION_JOB_STATUSES: frozenset[ExtractionJobStatus] = frozenset(
    {
        ExtractionJobStatus.QUEUED,
        ExtractionJobStatus.INSPECTING,
        ExtractionJobStatus.EXTRACTING,
        ExtractionJobStatus.NORMALISING,
        ExtractionJobStatus.PERSISTING,
        ExtractionJobStatus.CANCEL_REQUESTED,
    }
)


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ExtractionJob(Base):
    """One background extraction request and its safe status summary."""

    __tablename__ = "extraction_jobs"
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
        Index("ix_extraction_jobs_document_id", "document_id"),
        Index(
            "ix_extraction_jobs_document_revision_id",
            "document_revision_id",
        ),
        Index(
            "ix_extraction_jobs_document_file_id",
            "document_file_id",
        ),
        Index("ix_extraction_jobs_status", "status"),
        Index("ix_extraction_jobs_requested_by", "requested_by"),
        Index("ix_extraction_jobs_requested_at", "requested_at"),
        Index("ix_extraction_jobs_created_at", "created_at"),
        Index(
            "uq_extraction_jobs_one_active_per_file",
            "document_file_id",
            unique=True,
            postgresql_where=text(
                "status IN ('QUEUED', 'INSPECTING', 'EXTRACTING', "
                "'NORMALISING', 'PERSISTING', 'CANCEL_REQUESTED')"
            ),
            sqlite_where=text(
                "status IN ('QUEUED', 'INSPECTING', 'EXTRACTING', "
                "'NORMALISING', 'PERSISTING', 'CANCEL_REQUESTED')"
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
    job_type: Mapped[ExtractionJobType] = mapped_column(
        Enum(
            ExtractionJobType,
            name="extraction_job_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ExtractionJobType.INITIAL_EXTRACTION,
        server_default=ExtractionJobType.INITIAL_EXTRACTION.value,
    )
    status: Mapped[ExtractionJobStatus] = mapped_column(
        Enum(
            ExtractionJobStatus,
            name="extraction_job_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ExtractionJobStatus.QUEUED,
        server_default=ExtractionJobStatus.QUEUED.value,
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
    worker_reference: Mapped[str | None] = mapped_column(
        String(255),
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

    document: Mapped[Document] = relationship(
        back_populates="extraction_jobs",
        foreign_keys=[document_id],
    )
    revision: Mapped[DocumentRevision] = relationship(
        back_populates="extraction_jobs",
        foreign_keys=[document_revision_id],
    )
    document_file: Mapped[DocumentFile] = relationship(
        back_populates="extraction_jobs",
        foreign_keys=[document_file_id],
    )
    requester: Mapped[User | None] = relationship(
        back_populates="requested_extraction_jobs",
        foreign_keys=[requested_by],
    )
    extraction_run: Mapped[ExtractionRun | None] = relationship(
        back_populates="extraction_job",
        uselist=False,
        foreign_keys="ExtractionRun.extraction_job_id",
    )

    @validates("progress")
    def validate_progress(self, _: str, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("Extraction progress must be between 0 and 100.")
        return value
