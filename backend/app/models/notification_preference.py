"""Per-user notification channel and quiet-hour preferences."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import (
    NotificationDigestMode,
    NotificationEventType,
    enum_values,
)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "event_type",
            name="uq_notification_preferences_user_event",
        ),
        Index("ix_notification_preferences_user_id", "user_id"),
        Index("ix_notification_preferences_event_type", "event_type"),
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
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    teams_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    telegram_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    digest_mode: Mapped[NotificationDigestMode] = mapped_column(
        Enum(
            NotificationDigestMode,
            name="notification_digest_mode",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=NotificationDigestMode.NONE,
        server_default=NotificationDigestMode.NONE.value,
    )
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    quiet_hours_start: Mapped[time | None] = mapped_column(
        Time(timezone=False), nullable=True
    )
    quiet_hours_end: Mapped[time | None] = mapped_column(
        Time(timezone=False), nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(100), nullable=False, default="UTC", server_default="UTC"
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
