"""Remote SharePoint version audit independent of business revisions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SharePointFileVersion(Base):
    __tablename__ = "sharepoint_file_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_file_id",
            "remote_drive_id",
            "remote_item_id",
            "remote_version_id",
            name="uq_sharepoint_file_remote_version",
        ),
        Index("ix_sharepoint_file_versions_file", "document_file_id"),
        Index(
            "ix_sharepoint_file_versions_remote",
            "remote_drive_id",
            "remote_item_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    document_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    remote_drive_id: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    remote_item_id: Mapped[str] = mapped_column(String(1000), nullable=False)
    remote_version_id: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    remote_etag: Mapped[str | None] = mapped_column(String(1000))
    remote_last_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    remote_last_modified_by: Mapped[str | None] = mapped_column(String(500))
    remote_size: Mapped[int | None] = mapped_column(BigInteger)
    local_sha256_hash: Mapped[str | None] = mapped_column(String(64))
    sync_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_jobs.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
