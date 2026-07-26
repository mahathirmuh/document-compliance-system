"""Deterministic document-to-SharePoint folder mappings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import FolderMappingScope, enum_values


class SharePointFolderMapping(Base):
    __tablename__ = "sharepoint_folder_mappings"
    __table_args__ = (
        CheckConstraint(
            "priority >= 0",
            name="sharepoint_folder_mappings_priority_nonnegative",
        ),
        Index(
            "ix_sharepoint_folder_mappings_connection",
            "sharepoint_connection_id",
        ),
        Index(
            "ix_sharepoint_folder_mappings_resolution",
            "sharepoint_connection_id",
            "mapping_scope",
            "department_id",
            "section_id",
            "document_type_id",
            "priority",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sharepoint_connection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_connections.id", ondelete="CASCADE"),
        nullable=False,
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
    mapping_scope: Mapped[FolderMappingScope] = mapped_column(
        Enum(
            FolderMappingScope,
            name="sharepoint_folder_mapping_scope",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    remote_folder_path: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    remote_folder_id: Mapped[str | None] = mapped_column(String(1000))
    filename_pattern: Mapped[str | None] = mapped_column(String(500))
    create_folder_if_missing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
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
