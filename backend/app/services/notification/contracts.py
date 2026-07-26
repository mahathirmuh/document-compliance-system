"""Immutable contracts shared by notification services and adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationEventType,
    NotificationRecipientType,
    NotificationSeverity,
)


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    event_type: NotificationEventType
    severity: NotificationSeverity = NotificationSeverity.INFORMATION
    actor_id: UUID | None = None
    department_id: UUID | None = None
    document_type_id: UUID | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    action_url: str | None = None
    occurred_at: datetime | None = None
    variables: Mapping[str, Any] = field(default_factory=dict)
    recipient_context: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResolvedRecipient:
    recipient_type: NotificationRecipientType
    reference: str
    user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RenderedNotification:
    subject: str | None
    body: str
    content_type: NotificationContentType


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    event_type: NotificationEventType
    channel: NotificationChannel
    recipient: ResolvedRecipient
    subject: str | None
    body: str
    content_type: NotificationContentType
    severity: NotificationSeverity
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    action_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    succeeded: bool
    provider_message_id: str | None = None
    delivered: bool = False
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
