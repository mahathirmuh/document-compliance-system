"""Immutable OCR run summaries retained across re-OCR operations."""

from __future__ import annotations

import re
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
    Float,
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
from app.models.ocr_job import (
    OCRLanguageProfile,
    OCRPreprocessingProfile,
    _enum_values,
)

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.ocr_block import OCRBlock
    from app.models.ocr_job import OCRJob
    from app.models.ocr_page_result import OCRPageResult

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class OCRRunStatus(StrEnum):
    """Terminal status of a persisted OCR attempt."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OCRRun(Base):
    """One immutable, provenance-preserving OCR result."""

    __tablename__ = "ocr_runs"
    __table_args__ = (
        UniqueConstraint("ocr_job_id", name="uq_ocr_runs_ocr_job_id"),
        CheckConstraint(
            "page_count_requested >= 0 AND page_count_processed >= 0 "
            "AND page_count_failed >= 0 AND total_blocks >= 0 "
            "AND total_characters >= 0",
            name="ocr_run_counts_nonnegative",
        ),
        CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="ocr_run_average_confidence_range",
        ),
        CheckConstraint(
            "minimum_confidence IS NULL OR "
            "(minimum_confidence >= 0 AND minimum_confidence <= 1)",
            name="ocr_run_minimum_confidence_range",
        ),
        CheckConstraint(
            "maximum_confidence IS NULL OR "
            "(maximum_confidence >= 0 AND maximum_confidence <= 1)",
            name="ocr_run_maximum_confidence_range",
        ),
        CheckConstraint(
            "render_dpi >= 72",
            name="ocr_run_render_dpi_minimum",
        ),
        CheckConstraint(
            "length(source_sha256_hash) = 64",
            name="ocr_run_source_sha256_length",
        ),
        CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="ocr_run_content_hash_length",
        ),
        Index("ix_ocr_runs_document_id", "document_id"),
        Index("ix_ocr_runs_document_revision_id", "document_revision_id"),
        Index("ix_ocr_runs_document_file_id", "document_file_id"),
        Index(
            "ix_ocr_runs_source_extraction_run_id",
            "source_extraction_run_id",
        ),
        Index("ix_ocr_runs_status", "status"),
        Index("ix_ocr_runs_source_sha256_hash", "source_sha256_hash"),
        Index("ix_ocr_runs_content_hash", "content_hash"),
        Index("ix_ocr_runs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ocr_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_jobs.id", ondelete="RESTRICT"),
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
    source_extraction_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    language_profile: Mapped[OCRLanguageProfile] = mapped_column(
        Enum(
            OCRLanguageProfile,
            name="ocr_language_profile",
            values_callable=_enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    status: Mapped[OCRRunStatus] = mapped_column(
        Enum(
            OCRRunStatus,
            name="ocr_run_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_sha256_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    page_count_requested: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    page_count_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    page_count_failed: Mapped[int] = mapped_column(
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
    total_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    average_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    minimum_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    maximum_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    render_dpi: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        server_default="300",
    )
    preprocessing_profile: Mapped[OCRPreprocessingProfile] = mapped_column(
        Enum(
            OCRPreprocessingProfile,
            name="ocr_preprocessing_profile",
            values_callable=_enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
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
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ocr_job: Mapped[OCRJob] = relationship(
        back_populates="ocr_run",
        foreign_keys=[ocr_job_id],
    )
    document: Mapped[Document] = relationship(foreign_keys=[document_id])
    revision: Mapped[DocumentRevision] = relationship(
        foreign_keys=[document_revision_id]
    )
    document_file: Mapped[DocumentFile] = relationship(foreign_keys=[document_file_id])
    source_extraction_run: Mapped[ExtractionRun] = relationship(
        foreign_keys=[source_extraction_run_id]
    )
    pages: Mapped[list[OCRPageResult]] = relationship(
        back_populates="ocr_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OCRPageResult.page_number",
    )
    blocks: Mapped[list[OCRBlock]] = relationship(
        back_populates="ocr_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OCRBlock.ocr_page_result_id, OCRBlock.block_order",
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

    @validates(
        "average_confidence",
        "minimum_confidence",
        "maximum_confidence",
    )
    def validate_confidence(
        self,
        _: str,
        value: float | None,
    ) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("OCR confidence must be between 0 and 1.")
        return value
