"""Per-item SharePoint sync audit and idempotency state."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    SyncItemOperation,
    SyncItemStatus,
    enum_values,
)


class SharePointSyncItem(Base):
    __tablename__ = "sharepoint_sync_items"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_sharepoint_sync_items_idempotency_key",
        ),
        Index("ix_sharepoint_sync_items_job", "sync_job_id"),
        Index("ix_sharepoint_sync_items_file", "document_file_id"),
        Index(
            "ix_sharepoint_sync_items_remote",
            "remote_drive_id",
            "remote_item_id",
        ),
        Index("ix_sharepoint_sync_items_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sync_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    document_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="SET NULL"),
    )
    document_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="SET NULL"),
    )
    remote_drive_id: Mapped[str | None] = mapped_column(String(1000))
    remote_item_id: Mapped[str | None] = mapped_column(String(1000))
    remote_path: Mapped[str | None] = mapped_column(String(2000))
    operation: Mapped[SyncItemOperation] = mapped_column(
        Enum(
            SyncItemOperation,
            name="sharepoint_sync_item_operation",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[SyncItemStatus] = mapped_column(
        Enum(
            SyncItemStatus,
            name="sharepoint_sync_item_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SyncItemStatus.QUEUED,
        server_default=SyncItemStatus.QUEUED.value,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    local_hash_before: Mapped[str | None] = mapped_column(String(64))
    local_hash_after: Mapped[str | None] = mapped_column(String(64))
    remote_etag_before: Mapped[str | None] = mapped_column(String(1000))
    remote_etag_after: Mapped[str | None] = mapped_column(String(1000))
    remote_size: Mapped[int | None] = mapped_column(BigInteger)
    conflict_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "sharepoint_sync_conflicts.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_sharepoint_sync_items_conflict",
        ),
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
