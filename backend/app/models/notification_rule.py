"""Scoped notification routing rules."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import (
    NotificationChannel,
    NotificationEventType,
    NotificationRecipientType,
    NotificationScopeType,
    enum_values,
)


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'GLOBAL' AND department_id IS NULL "
            "AND document_type_id IS NULL) OR "
            "(scope_type = 'DEPARTMENT' AND department_id IS NOT NULL "
            "AND document_type_id IS NULL) OR "
            "(scope_type = 'DOCUMENT_TYPE' AND department_id IS NULL "
            "AND document_type_id IS NOT NULL) OR "
            "(scope_type = 'DEPARTMENT_DOCUMENT_TYPE' "
            "AND department_id IS NOT NULL "
            "AND document_type_id IS NOT NULL)",
            name="notification_rules_scope_consistent",
        ),
        Index("ix_notification_rules_event_type", "event_type"),
        Index("ix_notification_rules_channel", "channel"),
        Index("ix_notification_rules_department_id", "department_id"),
        Index("ix_notification_rules_document_type_id", "document_type_id"),
        Index("ix_notification_rules_is_active", "is_active"),
        Index(
            "ix_notification_rules_resolution",
            "event_type",
            "department_id",
            "document_type_id",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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
    scope_type: Mapped[NotificationScopeType] = mapped_column(
        Enum(
            NotificationScopeType,
            name="notification_scope_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=NotificationScopeType.GLOBAL,
        server_default=NotificationScopeType.GLOBAL.value,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=True,
    )
    severity_filter_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    recipient_type: Mapped[NotificationRecipientType] = mapped_column(
        Enum(
            NotificationRecipientType,
            name="notification_recipient_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    recipient_value_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    send_immediately: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    digest_schedule: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(
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
