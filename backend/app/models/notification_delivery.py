"""Auditable asynchronous notification delivery attempts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationRecipientType,
    enum_values,
)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0 AND maximum_attempts >= 1 "
            "AND attempt_count <= maximum_attempts",
            name="notification_deliveries_attempt_range",
        ),
        CheckConstraint(
            "length(payload_hash) = 64",
            name="notification_deliveries_payload_hash_length",
        ),
        Index("ix_notification_deliveries_event_type", "event_type"),
        Index("ix_notification_deliveries_channel", "channel"),
        Index("ix_notification_deliveries_status", "status"),
        Index("ix_notification_deliveries_created_at", "created_at"),
        Index("ix_notification_deliveries_next_retry_at", "next_retry_at"),
        Index(
            "ix_notification_deliveries_retry_queue",
            "status",
            "next_retry_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
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
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    template_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_type: Mapped[NotificationRecipientType] = mapped_column(
        Enum(
            NotificationRecipientType,
            name="notification_recipient_type",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    recipient_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        Enum(
            NotificationDeliveryStatus,
            name="notification_delivery_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=NotificationDeliveryStatus.QUEUED,
        server_default=NotificationDeliveryStatus.QUEUED.value,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    maximum_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
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
