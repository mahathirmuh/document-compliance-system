"""Private in-app notifications addressed to one authenticated user."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import (
    NotificationEventType,
    NotificationSeverity,
    enum_values,
)


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"
    __table_args__ = (
        Index("ix_in_app_notifications_user_id", "user_id"),
        Index("ix_in_app_notifications_event_type", "event_type"),
        Index("ix_in_app_notifications_is_read", "is_read"),
        Index("ix_in_app_notifications_created_at", "created_at"),
        Index("ix_in_app_notifications_expires_at", "expires_at"),
        Index(
            "ix_in_app_notifications_user_unread",
            "user_id",
            "is_read",
            "dismissed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[NotificationEventType] = mapped_column(
        Enum(
            NotificationEventType,
            name="notification_event_type",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(
        Enum(
            NotificationSeverity,
            name="notification_severity",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=NotificationSeverity.INFORMATION,
        server_default=NotificationSeverity.INFORMATION.value,
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    action_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
