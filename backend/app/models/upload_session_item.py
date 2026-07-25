"""Per-file validation and identification state for upload previews."""

from __future__ import annotations

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
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_revision import DocumentRevision
    from app.models.upload_session import UploadSession


class UploadIdentificationStatus(StrEnum):
    IDENTIFIED = "IDENTIFIED"
    PARTIALLY_IDENTIFIED = "PARTIALLY_IDENTIFIED"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    DUPLICATE_FILE = "DUPLICATE_FILE"
    INVALID = "INVALID"


class UploadProposedAction(StrEnum):
    ATTACH_TO_EXISTING_REVISION = "ATTACH_TO_EXISTING_REVISION"
    CREATE_DOCUMENT_AND_REVISION = "CREATE_DOCUMENT_AND_REVISION"
    ADD_NEW_REVISION = "ADD_NEW_REVISION"
    REPLACE_CURRENT_FILE = "REPLACE_CURRENT_FILE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    SKIP = "SKIP"


class UploadSessionItemStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    COMMITTED = "COMMITTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class UploadSessionItem(Base):
    """One temporary file and its preview/confirmation result."""

    __tablename__ = "upload_session_items"
    __table_args__ = (
        UniqueConstraint(
            "temporary_storage_key",
            name="uq_upload_session_items_temporary_storage_key",
        ),
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="file_size_nonnegative",
        ),
        CheckConstraint(
            "sha256_hash IS NULL OR length(sha256_hash) = 64",
            name="sha256_length",
        ),
        Index(
            "ix_upload_session_items_upload_session_id",
            "upload_session_id",
        ),
        Index(
            "ix_upload_session_items_identification_status",
            "identification_status",
        ),
        Index("ix_upload_session_items_status", "status"),
        Index(
            "ix_upload_session_items_matched_document_id",
            "matched_document_id",
        ),
        Index(
            "ix_upload_session_items_matched_revision_id",
            "matched_revision_id",
        ),
        Index("ix_upload_session_items_sha256_hash", "sha256_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    upload_session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    temporary_storage_key: Mapped[str] = mapped_column(
        String(1000),
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
    file_extension: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    detected_mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    identification_status: Mapped[UploadIdentificationStatus] = mapped_column(
        Enum(
            UploadIdentificationStatus,
            name="upload_identification_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UploadIdentificationStatus.NOT_IDENTIFIED,
        server_default=UploadIdentificationStatus.NOT_IDENTIFIED.value,
    )
    matched_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_action: Mapped[UploadProposedAction] = mapped_column(
        Enum(
            UploadProposedAction,
            name="upload_proposed_action",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UploadProposedAction.SKIP,
        server_default=UploadProposedAction.SKIP.value,
    )
    parsed_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    warnings_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    errors_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    quarantine_reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    temporary_cleanup_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[UploadSessionItemStatus] = mapped_column(
        Enum(
            UploadSessionItemStatus,
            name="upload_session_item_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UploadSessionItemStatus.PENDING,
        server_default=UploadSessionItemStatus.PENDING.value,
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

    upload_session: Mapped[UploadSession] = relationship(
        back_populates="items",
        foreign_keys=[upload_session_id],
    )
    matched_document: Mapped[Document | None] = relationship(
        foreign_keys=[matched_document_id],
    )
    matched_revision: Mapped[DocumentRevision | None] = relationship(
        foreign_keys=[matched_revision_id],
    )
