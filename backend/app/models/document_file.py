"""Private physical-file metadata linked to one document revision."""

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
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_job import ExtractionJob
    from app.models.extraction_run import ExtractionRun
    from app.models.language_detection_run import LanguageDetectionRun
    from app.models.ocr_run import OCRRun
    from app.models.user import User

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DocumentFileStatus(StrEnum):
    UPLOADING = "UPLOADING"
    AVAILABLE = "AVAILABLE"
    QUARANTINED = "QUARANTINED"
    REPLACED = "REPLACED"
    DELETED = "DELETED"
    FAILED = "FAILED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class DocumentFile(Base):
    """Metadata only; content remains private behind ``BaseStorage``."""

    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint(
            "storage_key",
            name="uq_document_files_storage_key",
        ),
        CheckConstraint(
            "file_size >= 0",
            name="file_size_nonnegative",
        ),
        CheckConstraint(
            "length(sha256_hash) = 64",
            name="sha256_length",
        ),
        Index("ix_document_files_document_id", "document_id"),
        Index(
            "ix_document_files_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_document_files_sha256_hash", "sha256_hash"),
        Index("ix_document_files_file_status", "file_status"),
        Index("ix_document_files_is_current", "is_current"),
        Index("ix_document_files_uploaded_at", "uploaded_at"),
        Index(
            "ix_document_files_latest_extraction_run_id",
            "latest_extraction_run_id",
        ),
        Index(
            "ix_document_files_latest_ocr_run_id",
            "latest_ocr_run_id",
        ),
        Index(
            "ix_document_files_latest_language_detection_run_id",
            "latest_language_detection_run_id",
        ),
        Index(
            "uq_document_files_one_current_primary",
            "document_revision_id",
            unique=True,
            postgresql_where=text(
                "is_current IS TRUE AND is_primary IS TRUE "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "is_current = 1 AND is_primary = 1 AND deleted_at IS NULL"
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
    original_filename: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    sanitized_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="local",
        server_default="local",
    )
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_bucket: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    file_status: Mapped[DocumentFileStatus] = mapped_column(
        Enum(
            DocumentFileStatus,
            name="document_file_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=DocumentFileStatus.UPLOADING,
        server_default=DocumentFileStatus.UPLOADING.value,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "document_files.id",
            name="fk_document_files_replaced_by_file_id_document_files",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deletion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    latest_extraction_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "extraction_runs.id",
            name=(
                "fk_document_files_latest_extraction_run_id_"
                "extraction_runs"
            ),
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    latest_ocr_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "ocr_runs.id",
            name="fk_document_files_latest_ocr_run_id_ocr_runs",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    latest_language_detection_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "language_detection_runs.id",
            name=(
                "fk_document_files_latest_language_detection_run_id_"
                "language_detection_runs"
            ),
            ondelete="SET NULL",
            use_alter=True,
        ),
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
        back_populates="files",
        foreign_keys=[document_id],
    )
    revision: Mapped[DocumentRevision] = relationship(
        back_populates="files",
        foreign_keys=[document_revision_id],
    )
    uploader: Mapped[User | None] = relationship(
        back_populates="uploaded_document_files",
        foreign_keys=[uploaded_by],
    )
    deleter: Mapped[User | None] = relationship(
        back_populates="deleted_document_files",
        foreign_keys=[deleted_by],
    )
    replaced_by_file: Mapped[DocumentFile | None] = relationship(
        remote_side=[id],
        foreign_keys=[replaced_by_file_id],
    )
    extraction_jobs: Mapped[list[ExtractionJob]] = relationship(
        back_populates="document_file",
        foreign_keys="ExtractionJob.document_file_id",
        passive_deletes=True,
        order_by="ExtractionJob.requested_at",
    )
    extraction_runs: Mapped[list[ExtractionRun]] = relationship(
        back_populates="document_file",
        foreign_keys="ExtractionRun.document_file_id",
        passive_deletes=True,
        order_by="ExtractionRun.created_at",
    )
    latest_extraction_run: Mapped[ExtractionRun | None] = relationship(
        foreign_keys=[latest_extraction_run_id],
        post_update=True,
    )
    latest_ocr_run: Mapped[OCRRun | None] = relationship(
        foreign_keys=[latest_ocr_run_id],
        post_update=True,
    )
    latest_language_detection_run: Mapped[
        LanguageDetectionRun | None
    ] = relationship(
        foreign_keys=[latest_language_detection_run_id],
        post_update=True,
    )

    @validates("file_extension")
    def normalize_extension(self, _: str, value: str) -> str:
        normalized = value.strip().lower().lstrip(".")
        if normalized not in {"pdf", "docx", "xlsx"}:
            raise ValueError("Unsupported document file extension.")
        return normalized

    @validates("sha256_hash")
    def normalize_sha256(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("SHA-256 hash must be 64 lowercase hex digits.")
        return normalized
