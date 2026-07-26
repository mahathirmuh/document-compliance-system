"""Non-secret SharePoint site and document-library configuration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    SharePointAuthMode,
    SharePointConnectionStatus,
    enum_values,
)


class SharePointConnection(Base):
    __tablename__ = "sharepoint_connections"
    __table_args__ = (
        Index("ix_sharepoint_connections_status", "status"),
        Index("ix_sharepoint_connections_active", "is_active"),
        Index(
            "uq_sharepoint_connections_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default IS TRUE AND is_active IS TRUE"),
            sqlite_where=text("is_default = 1 AND is_active = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    tenant_id_reference: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    site_hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    site_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    site_id: Mapped[str | None] = mapped_column(String(1000))
    drive_id: Mapped[str | None] = mapped_column(String(1000))
    library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    root_folder_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        default="DocumentCompliance",
        server_default="DocumentCompliance",
    )
    auth_mode: Mapped[SharePointAuthMode] = mapped_column(
        Enum(
            SharePointAuthMode,
            name="sharepoint_auth_mode",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SharePointAuthMode.CLIENT_SECRET,
        server_default=SharePointAuthMode.CLIENT_SECRET.value,
    )
    status: Mapped[SharePointConnectionStatus] = mapped_column(
        Enum(
            SharePointConnectionStatus,
            name="sharepoint_connection_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SharePointConnectionStatus.NOT_CONFIGURED,
        server_default=SharePointConnectionStatus.NOT_CONFIGURED.value,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_test_status: Mapped[str | None] = mapped_column(String(100))
    last_test_message: Mapped[str | None] = mapped_column(Text)
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
