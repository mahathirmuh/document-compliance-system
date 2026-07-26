"""Internal-field SharePoint list-column mappings."""

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
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    MetadataDataType,
    MetadataDirection,
    enum_values,
)


class SharePointMetadataMapping(Base):
    __tablename__ = "sharepoint_metadata_mappings"
    __table_args__ = (
        UniqueConstraint(
            "sharepoint_connection_id",
            "document_field",
            "sharepoint_field_internal_name",
            name="uq_sharepoint_metadata_mapping_fields",
        ),
        Index(
            "ix_sharepoint_metadata_mappings_connection",
            "sharepoint_connection_id",
        ),
        Index(
            "ix_sharepoint_metadata_mappings_active",
            "is_active",
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
    document_field: Mapped[str] = mapped_column(String(255), nullable=False)
    sharepoint_field_internal_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    data_type: Mapped[MetadataDataType] = mapped_column(
        Enum(
            MetadataDataType,
            name="sharepoint_metadata_data_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=MetadataDataType.STRING,
        server_default=MetadataDataType.STRING.value,
    )
    direction: Mapped[MetadataDirection] = mapped_column(
        Enum(
            MetadataDirection,
            name="sharepoint_metadata_direction",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=MetadataDirection.OUTBOUND,
        server_default=MetadataDirection.OUTBOUND.value,
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    default_value: Mapped[dict[str, Any] | str | int | bool | None] = (
        mapped_column(JSON().with_variant(JSONB, "postgresql"))
    )
    transformer_code: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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
