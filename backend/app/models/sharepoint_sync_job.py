"""Durable SharePoint sync job lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    ACTIVE_SYNC_JOB_STATUSES,
    SharePointSyncJobStatus,
    SyncDirection,
    SyncJobType,
    enum_values,
)

_ACTIVE_SQL = ", ".join(
    f"'{status.value}'" for status in ACTIVE_SYNC_JOB_STATUSES
)


class SharePointSyncJob(Base):
    __tablename__ = "sharepoint_sync_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="sharepoint_sync_jobs_progress_range",
        ),
        CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= 1 "
            "AND attempt_number <= maximum_attempts",
            name="sharepoint_sync_jobs_attempt_range",
        ),
        Index("ix_sharepoint_sync_jobs_profile", "sync_profile_id"),
        Index("ix_sharepoint_sync_jobs_connection", "sharepoint_connection_id"),
        Index("ix_sharepoint_sync_jobs_status", "status"),
        Index("ix_sharepoint_sync_jobs_requested_at", "requested_at"),
        Index(
            "uq_sharepoint_sync_jobs_active_profile",
            "sync_profile_id",
            unique=True,
            postgresql_where=text(f"status IN ({_ACTIVE_SQL})"),
            sqlite_where=text(f"status IN ({_ACTIVE_SQL})"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sync_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sharepoint_connection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_type: Mapped[SyncJobType] = mapped_column(
        Enum(
            SyncJobType,
            name="sharepoint_sync_job_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    direction: Mapped[SyncDirection] = mapped_column(
        Enum(
            SyncDirection,
            name="sharepoint_sync_job_direction",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[SharePointSyncJobStatus] = mapped_column(
        Enum(
            SharePointSyncJobStatus,
            name="sharepoint_sync_job_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SharePointSyncJobStatus.QUEUED,
        server_default=SharePointSyncJobStatus.QUEUED.value,
    )
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_stage: Mapped[str | None] = mapped_column(String(500))
    scope_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    maximum_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    delta_token_before: Mapped[str | None] = mapped_column(String(64))
    delta_token_after: Mapped[str | None] = mapped_column(String(64))
    items_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_conflicted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
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
