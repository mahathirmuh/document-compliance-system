"""Durable successful, partial, or OCR-required extraction result."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
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
    from app.models.extracted_block import ExtractedBlock
    from app.models.extracted_container import ExtractedContainer
    from app.models.extracted_table import ExtractedTable
    from app.models.extraction_job import ExtractionJob

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ExtractorType(StrEnum):
    """Supported Phase 6 extraction engines."""

    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"


class ExtractionRunStatus(StrEnum):
    """Statuses that can retain a durable extraction run."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    OCR_REQUIRED = "OCR_REQUIRED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ExtractionRun(Base):
    """Immutable extraction result retained across re-extractions."""

    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "extraction_job_id",
            name="uq_extraction_runs_extraction_job_id",
        ),
        CheckConstraint(
            "source_file_size >= 0",
            name="source_file_size_nonnegative",
        ),
        CheckConstraint(
            "length(source_sha256_hash) = 64",
            name="source_sha256_length",
        ),
        CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="content_hash_length",
        ),
        CheckConstraint(
            "total_pages >= 0 AND total_sheets >= 0 "
            "AND total_blocks >= 0 AND total_paragraphs >= 0 "
            "AND total_tables >= 0 AND total_cells >= 0 "
            "AND total_characters >= 0 AND total_words >= 0",
            name="summary_counts_nonnegative",
        ),
        Index("ix_extraction_runs_document_id", "document_id"),
        Index(
            "ix_extraction_runs_document_revision_id",
            "document_revision_id",
        ),
        Index(
            "ix_extraction_runs_document_file_id",
            "document_file_id",
        ),
        Index("ix_extraction_runs_status", "status"),
        Index(
            "ix_extraction_runs_source_sha256_hash",
            "source_sha256_hash",
        ),
        Index("ix_extraction_runs_content_hash", "content_hash"),
        Index("ix_extraction_runs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    extraction_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_jobs.id", ondelete="RESTRICT"),
        nullable=False,
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
    extractor_type: Mapped[ExtractorType] = mapped_column(
        Enum(
            ExtractorType,
            name="extraction_extractor_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    extractor_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[ExtractionRunStatus] = mapped_column(
        Enum(
            ExtractionRunStatus,
            name="extraction_run_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_sha256_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    source_file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    total_pages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_sheets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_paragraphs: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_tables: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_cells: Mapped[int] = mapped_column(
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
    total_words: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    has_selectable_text: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    requires_ocr: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    warnings_json: Mapped[list[dict[str, Any]] | list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
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

    extraction_job: Mapped[ExtractionJob] = relationship(
        back_populates="extraction_run",
        foreign_keys=[extraction_job_id],
    )
    document: Mapped[Document] = relationship(
        back_populates="extraction_runs",
        foreign_keys=[document_id],
    )
    revision: Mapped[DocumentRevision] = relationship(
        back_populates="extraction_runs",
        foreign_keys=[document_revision_id],
    )
    document_file: Mapped[DocumentFile] = relationship(
        back_populates="extraction_runs",
        foreign_keys=[document_file_id],
    )
    containers: Mapped[list[ExtractedContainer]] = relationship(
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedContainer.container_index",
    )
    blocks: Mapped[list[ExtractedBlock]] = relationship(
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedBlock.block_order",
    )
    tables: Mapped[list[ExtractedTable]] = relationship(
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedTable.table_index",
    )

    @validates("source_sha256_hash", "content_hash")
    def normalize_hash(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        if value is None and key == "content_hash":
            return None
        normalized = (value or "").strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError(f"{key} must be 64 lowercase hex digits.")
        return normalized
