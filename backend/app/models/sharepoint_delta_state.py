"""Encrypted-at-rest SharePoint delta cursor state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base


class SharePointDeltaState(Base):
    __tablename__ = "sharepoint_delta_states"
    __table_args__ = (
        UniqueConstraint(
            "sync_profile_id",
            "drive_id",
            "folder_item_id",
            name="uq_sharepoint_delta_state_scope",
        ),
        CheckConstraint(
            "length(delta_token_hash) = 64",
            name="sharepoint_delta_state_hash_length",
        ),
        Index("ix_sharepoint_delta_states_valid", "is_valid"),
        Index("ix_sharepoint_delta_states_synced_at", "last_synced_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sync_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    drive_id: Mapped[str] = mapped_column(String(1000), nullable=False)
    folder_item_id: Mapped[str | None] = mapped_column(String(1000))
    delta_link_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    delta_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_successful_sync_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_jobs.id", ondelete="SET NULL"),
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    invalidation_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @validates("delta_link_encrypted")
    def forbid_plain_delta_link(self, _: str, value: str) -> str:
        normalized = value.strip()
        if normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Delta links must be encrypted before persistence.")
        if not normalized:
            raise ValueError("Encrypted delta state is required.")
        return normalized
