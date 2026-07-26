"""Versioned safe notification templates."""

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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base
from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationEventType,
    enum_values,
)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint(
            "code",
            "version",
            "channel",
            "language_code",
            name="uq_notification_templates_code_version_channel_language",
        ),
        CheckConstraint(
            "version >= 1",
            name="notification_templates_version_positive",
        ),
        Index("ix_notification_templates_event_type", "event_type"),
        Index("ix_notification_templates_channel", "channel"),
        Index("ix_notification_templates_is_active", "is_active"),
        Index(
            "ix_notification_templates_resolution",
            "event_type",
            "channel",
            "language_code",
            "is_default",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[NotificationEventType] = mapped_column(
        Enum(
            NotificationEventType,
            name="notification_event_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    subject_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[NotificationContentType] = mapped_column(
        Enum(
            NotificationContentType,
            name="notification_content_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=NotificationContentType.PLAIN_TEXT,
        server_default=NotificationContentType.PLAIN_TEXT.value,
    )
    language_code: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en", server_default="en"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Notification template code is required.")
        return normalized

    @validates("language_code")
    def normalize_language(self, _: str, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"id", "en", "zh"}:
            raise ValueError("Notification language must be id, en, or zh.")
        return normalized
