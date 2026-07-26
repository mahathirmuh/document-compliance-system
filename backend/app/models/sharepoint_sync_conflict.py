"""Manual and policy-driven SharePoint conflict workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    SyncConflictResolution,
    SyncConflictStatus,
    SyncConflictType,
    enum_values,
)


class SharePointSyncConflict(Base):
    __tablename__ = "sharepoint_sync_conflicts"
    __table_args__ = (
        Index("ix_sharepoint_sync_conflicts_job", "sync_job_id"),
        Index("ix_sharepoint_sync_conflicts_file", "document_file_id"),
        Index("ix_sharepoint_sync_conflicts_status", "status"),
        Index("ix_sharepoint_sync_conflicts_detected", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sync_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_item_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "sharepoint_sync_items.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_sharepoint_sync_conflicts_item",
        ),
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
    remote_item_id: Mapped[str | None] = mapped_column(String(1000))
    conflict_type: Mapped[SyncConflictType] = mapped_column(
        Enum(
            SyncConflictType,
            name="sharepoint_sync_conflict_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[SyncConflictStatus] = mapped_column(
        Enum(
            SyncConflictStatus,
            name="sharepoint_sync_conflict_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SyncConflictStatus.OPEN,
        server_default=SyncConflictStatus.OPEN.value,
    )
    local_version_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    remote_version_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution: Mapped[SyncConflictResolution | None] = mapped_column(
        Enum(
            SyncConflictResolution,
            name="sharepoint_sync_conflict_resolution",
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_comment: Mapped[str | None] = mapped_column(Text)
    result_document_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
