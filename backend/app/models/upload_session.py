"""Two-stage single, batch, and replacement upload sessions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.upload_session_item import UploadSessionItem
    from app.models.user import User


class UploadSessionType(StrEnum):
    SINGLE = "SINGLE"
    BATCH = "BATCH"
    REPLACE = "REPLACE"


class UploadSessionStatus(StrEnum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    COMMITTED = "COMMITTED"
    PARTIALLY_COMMITTED = "PARTIALLY_COMMITTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class UploadSession(Base):
    """Temporary preview state owned by one authenticated user."""

    __tablename__ = "upload_sessions"
    __table_args__ = (
        CheckConstraint(
            "total_files >= 0",
            name="total_files_nonnegative",
        ),
        CheckConstraint(
            "total_size >= 0",
            name="total_size_nonnegative",
        ),
        Index("ix_upload_sessions_user_id", "user_id"),
        Index("ix_upload_sessions_status", "status"),
        Index("ix_upload_sessions_expires_at", "expires_at"),
        Index("ix_upload_sessions_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_type: Mapped[UploadSessionType] = mapped_column(
        Enum(
            UploadSessionType,
            name="upload_session_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[UploadSessionStatus] = mapped_column(
        Enum(
            UploadSessionStatus,
            name="upload_session_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UploadSessionStatus.CREATED,
        server_default=UploadSessionStatus.CREATED.value,
    )
    total_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    committed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
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

    user: Mapped[User] = relationship(
        back_populates="upload_sessions",
        foreign_keys=[user_id],
    )
    items: Mapped[list[UploadSessionItem]] = relationship(
        back_populates="upload_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="UploadSessionItem.created_at",
    )
