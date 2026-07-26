"""Strict JSON payload accepted by the private notification queue."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationEventType,
    NotificationRecipientType,
    NotificationSeverity,
)
from app.schemas.base import ApiSchema
from app.services.notification.contracts import (
    NotificationMessage,
    ResolvedRecipient,
)


class NotificationTaskPayload(ApiSchema):
    event_type: NotificationEventType
    channel: NotificationChannel
    recipient_type: NotificationRecipientType
    recipient_reference: str = Field(min_length=1, max_length=1000)
    recipient_user_id: UUID | None = None
    subject: str | None = Field(default=None, max_length=500)
    body: str = Field(min_length=1, max_length=100_000)
    content_type: NotificationContentType
    severity: NotificationSeverity = NotificationSeverity.INFORMATION
    related_entity_type: str | None = Field(default=None, max_length=100)
    related_entity_id: UUID | None = None
    action_url: str | None = Field(default=None, max_length=2000)
    template_id: UUID | None = None
    request_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action_url")
    @classmethod
    def validate_internal_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if (
            not candidate.startswith("/")
            or candidate.startswith("//")
            or "\\" in candidate
            or "://" in candidate
        ):
            raise ValueError("actionUrl must be an internal route.")
        return candidate

    def to_message(self) -> NotificationMessage:
        return NotificationMessage(
            event_type=self.event_type,
            channel=self.channel,
            recipient=ResolvedRecipient(
                recipient_type=self.recipient_type,
                reference=self.recipient_reference,
                user_id=self.recipient_user_id,
            ),
            subject=self.subject,
            body=self.body,
            content_type=self.content_type,
            severity=self.severity,
            related_entity_type=self.related_entity_type,
            related_entity_id=self.related_entity_id,
            action_url=self.action_url,
            metadata=self.metadata,
        )
