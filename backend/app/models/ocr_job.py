"""Durable background OCR requests for scanned PDF pages."""

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
    from app.models.ocr_run import OCRRun
    from app.models.user import User


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class OCRJobType(StrEnum):
    """Reason an OCR request was queued."""

    INITIAL_OCR = "INITIAL_OCR"
    RE_OCR = "RE_OCR"
    MANUAL_PAGE_OCR = "MANUAL_PAGE_OCR"


class OCRJobStatus(StrEnum):
    """Lifecycle state stored independently from Celery."""

    QUEUED = "QUEUED"
    INSPECTING = "INSPECTING"
    RENDERING = "RENDERING"
    PREPROCESSING = "PREPROCESSING"
    RECOGNISING = "RECOGNISING"
    MERGING = "MERGING"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class OCRLanguageProfile(StrEnum):
    """Bounded model selection exposed to OCR clients."""

    LATIN = "LATIN"
    CHINESE_SIMPLIFIED = "CHINESE_SIMPLIFIED"
    AUTO_MULTILINGUAL = "AUTO_MULTILINGUAL"


class OCRPreprocessingProfile(StrEnum):
    """Supported local image-cleanup profiles."""

    NONE = "NONE"
    STANDARD = "STANDARD"
    AGGRESSIVE = "AGGRESSIVE"


ACTIVE_OCR_JOB_STATUSES: frozenset[OCRJobStatus] = frozenset(
    {
        OCRJobStatus.QUEUED,
        OCRJobStatus.INSPECTING,
        OCRJobStatus.RENDERING,
        OCRJobStatus.PREPROCESSING,
        OCRJobStatus.RECOGNISING,
        OCRJobStatus.MERGING,
        OCRJobStatus.PERSISTING,
        OCRJobStatus.CANCEL_REQUESTED,
    }
)


class OCRJob(Base):
    """One auditable OCR request for one immutable PDF source."""

    __tablename__ = "ocr_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ocr_job_progress_range",
        ),
        CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= 1 "
            "AND attempt_number <= maximum_attempts",
            name="ocr_job_attempt_range",
        ),
        Index("ix_ocr_jobs_document_id", "document_id"),
        Index("ix_ocr_jobs_document_revision_id", "document_revision_id"),
        Index("ix_ocr_jobs_document_file_id", "document_file_id"),
        Index("ix_ocr_jobs_extraction_run_id", "extraction_run_id"),
        Index("ix_ocr_jobs_status", "status"),
        Index("ix_ocr_jobs_requested_by", "requested_by"),
        Index("ix_ocr_jobs_requested_at", "requested_at"),
        Index("ix_ocr_jobs_created_at", "created_at"),
        Index(
            "uq_ocr_jobs_one_active_per_file",
            "document_file_id",
            unique=True,
            postgresql_where=text(
                "status IN ('QUEUED', 'INSPECTING', 'RENDERING', "
                "'PREPROCESSING', 'RECOGNISING', 'MERGING', "
                "'PERSISTING', 'CANCEL_REQUESTED')"
            ),
            sqlite_where=text(
                "status IN ('QUEUED', 'INSPECTING', 'RENDERING', "
                "'PREPROCESSING', 'RECOGNISING', 'MERGING', "
                "'PERSISTING', 'CANCEL_REQUESTED')"
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
    job_type: Mapped[OCRJobType] = mapped_column(
        Enum(
            OCRJobType,
            name="ocr_job_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=OCRJobType.INITIAL_OCR,
        server_default=OCRJobType.INITIAL_OCR.value,
    )
    status: Mapped[OCRJobStatus] = mapped_column(
        Enum(
            OCRJobStatus,
            name="ocr_job_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=OCRJobStatus.QUEUED,
        server_default=OCRJobStatus.QUEUED.value,
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
    language_profile: Mapped[OCRLanguageProfile] = mapped_column(
        Enum(
            OCRLanguageProfile,
            name="ocr_language_profile",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=OCRLanguageProfile.AUTO_MULTILINGUAL,
        server_default=OCRLanguageProfile.AUTO_MULTILINGUAL.value,
    )
    preprocessing_profile: Mapped[OCRPreprocessingProfile] = mapped_column(
        Enum(
            OCRPreprocessingProfile,
            name="ocr_preprocessing_profile",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=OCRPreprocessingProfile.STANDARD,
        server_default=OCRPreprocessingProfile.STANDARD.value,
    )
    requested_page_numbers_json: Mapped[list[int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    processed_page_numbers_json: Mapped[list[int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    failed_page_numbers_json: Mapped[list[int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
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
        default=2,
        server_default="2",
    )
    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="paddleocr",
        server_default="paddleocr",
    )
    provider_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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
    document_file: Mapped[DocumentFile] = relationship(foreign_keys=[document_file_id])
    extraction_run: Mapped[ExtractionRun] = relationship(
        foreign_keys=[extraction_run_id]
    )
    requester: Mapped[User | None] = relationship(foreign_keys=[requested_by])
    ocr_run: Mapped[OCRRun | None] = relationship(
        back_populates="ocr_job",
        uselist=False,
        foreign_keys="OCRRun.ocr_job_id",
    )

    @validates("progress")
    def validate_progress(self, _: str, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("OCR progress must be between 0 and 100.")
        return value

    @validates(
        "requested_page_numbers_json",
        "processed_page_numbers_json",
        "failed_page_numbers_json",
    )
    def validate_page_numbers(self, _: str, value: list[int]) -> list[int]:
        if any(
            isinstance(page, bool) or not isinstance(page, int) or page < 1
            for page in value
        ):
            raise ValueError("OCR page numbers must be positive integers.")
        if len(value) != len(set(value)):
            raise ValueError("OCR page numbers must be unique.")
        return sorted(value)
