"""SharePoint synchronisation policy and scope."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base
from app.models.sharepoint_enums import (
    ConflictPolicy,
    DeletePolicy,
    FolderMappingScope,
    SyncDirection,
    enum_values,
)


class SharePointSyncProfile(Base):
    __tablename__ = "sharepoint_sync_profiles"
    __table_args__ = (
        Index(
            "ix_sharepoint_sync_profiles_connection",
            "sharepoint_connection_id",
        ),
        Index(
            "ix_sharepoint_sync_profiles_scope",
            "scope_type",
            "department_id",
            "section_id",
            "document_type_id",
        ),
        Index("ix_sharepoint_sync_profiles_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sharepoint_connection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    direction: Mapped[SyncDirection] = mapped_column(
        Enum(
            SyncDirection,
            name="sharepoint_sync_direction",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SyncDirection.OUTBOUND,
        server_default=SyncDirection.OUTBOUND.value,
    )
    scope_type: Mapped[FolderMappingScope] = mapped_column(
        Enum(
            FolderMappingScope,
            name="sharepoint_sync_scope_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=FolderMappingScope.GLOBAL,
        server_default=FolderMappingScope.GLOBAL.value,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE")
    )
    section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE")
    )
    document_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="CASCADE"),
    )
    folder_mapping_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_folder_mappings.id", ondelete="SET NULL"),
    )
    metadata_mapping_profile: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    conflict_policy: Mapped[ConflictPolicy] = mapped_column(
        Enum(
            ConflictPolicy,
            name="sharepoint_conflict_policy",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ConflictPolicy.MANUAL,
        server_default=ConflictPolicy.MANUAL.value,
    )
    delete_policy: Mapped[DeletePolicy] = mapped_column(
        Enum(
            DeletePolicy,
            name="sharepoint_delete_policy",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=DeletePolicy.IGNORE_REMOTE_DELETE,
        server_default=DeletePolicy.IGNORE_REMOTE_DELETE.value,
    )
    sync_schedule: Mapped[str | None] = mapped_column(String(255))
    delta_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    webhook_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
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

    @validates("conflict_policy", "direction")
    def validate_bidirectional(
        self,
        key: str,
        value: ConflictPolicy | SyncDirection,
    ) -> ConflictPolicy | SyncDirection:
        direction = (
            value
            if key == "direction"
            else getattr(self, "direction", SyncDirection.OUTBOUND)
        )
        policy = (
            value
            if key == "conflict_policy"
            else getattr(self, "conflict_policy", ConflictPolicy.MANUAL)
        )
        if (
            direction is SyncDirection.BIDIRECTIONAL
            and policy is None
        ):
            raise ValueError(
                "Bidirectional sync requires an explicit conflict policy."
            )
        return value
