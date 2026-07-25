"""Immutable Phase 7 language detection run summaries."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.language_block_result import LanguageBlockResult
    from app.models.language_container_summary import (
        LanguageContainerSummary,
    )
    from app.models.language_detection_job import LanguageDetectionJob
    from app.models.user import User


class LanguageDetectionRunStatus(StrEnum):
    """Durable result states."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class LanguageDetectionRun(Base):
    """One retained language-analysis result over a merged content snapshot."""

    __tablename__ = "language_detection_runs"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_language_detection_runs_job_id"),
        CheckConstraint(
            "length(source_content_hash) = 64",
            name="source_content_hash_length",
        ),
        CheckConstraint(
            "total_blocks >= 0 AND eligible_blocks >= 0 "
            "AND detected_blocks >= 0 AND unknown_blocks >= 0 "
            "AND mixed_blocks >= 0 AND indonesian_blocks >= 0 "
            "AND english_blocks >= 0 AND chinese_blocks >= 0 "
            "AND other_blocks >= 0",
            name="block_counts_nonnegative",
        ),
        CheckConstraint(
            "eligible_blocks <= total_blocks "
            "AND detected_blocks <= eligible_blocks",
            name="block_count_bounds",
        ),
        CheckConstraint(
            "total_characters >= 0 AND indonesian_characters >= 0 "
            "AND english_characters >= 0 AND chinese_characters >= 0 "
            "AND mixed_characters >= 0 AND unknown_characters >= 0",
            name="character_counts_nonnegative",
        ),
        CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="average_confidence_range",
        ),
        Index("ix_language_detection_runs_document_id", "document_id"),
        Index(
            "ix_language_detection_runs_document_revision_id",
            "document_revision_id",
        ),
        Index(
            "ix_language_detection_runs_document_file_id",
            "document_file_id",
        ),
        Index(
            "ix_language_detection_runs_extraction_run_id",
            "extraction_run_id",
        ),
        Index("ix_language_detection_runs_ocr_run_id", "ocr_run_id"),
        Index("ix_language_detection_runs_status", "status"),
        Index(
            "ix_language_detection_runs_source_content_hash",
            "source_content_hash",
        ),
        Index("ix_language_detection_runs_created_at", "created_at"),
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
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    detector_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    detector_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[LanguageDetectionRunStatus] = mapped_column(
        Enum(
            LanguageDetectionRunStatus,
            name="language_detection_run_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    total_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    eligible_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    detected_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    unknown_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    mixed_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    indonesian_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    english_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    chinese_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    other_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    indonesian_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    english_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    chinese_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    mixed_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    unknown_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    average_confidence: Mapped[float | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )
    warnings_json: Mapped[list[str] | list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    job: Mapped[LanguageDetectionJob] = relationship(
        back_populates="detection_run",
        foreign_keys=[job_id],
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
    block_results: Mapped[list[LanguageBlockResult]] = relationship(
        back_populates="language_detection_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    container_summaries: Mapped[list[LanguageContainerSummary]] = (
        relationship(
            back_populates="language_detection_run",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by="LanguageContainerSummary.container_index",
        )
    )

    @validates("source_content_hash")
    def normalize_hash(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError(
                "source_content_hash must be 64 lowercase hex digits."
            )
        return normalized
