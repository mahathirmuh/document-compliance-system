"""Low-latency private in-app notification adapter."""

from __future__ import annotations

from app.models.in_app_notification import InAppNotification
from app.models.notification_enums import NotificationChannel
from app.repositories.in_app_notification_repository import (
    InAppNotificationRepository,
)
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)


def _internal_action_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or "://" in candidate
    ):
        return None
    return candidate[:2000]


class InAppNotificationChannel(BaseNotificationChannel):
    channel = NotificationChannel.IN_APP

    def __init__(self, repository: InAppNotificationRepository) -> None:
        self.repository = repository

    async def send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> DeliveryResult:
        if message.recipient.user_id is None:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_RECIPIENT_NOT_FOUND",
                error_message="In-app recipient must reference a user.",
                retryable=False,
            )
        notification = await self.repository.add(
            InAppNotification(
                user_id=message.recipient.user_id,
                event_type=message.event_type,
                title=(message.subject or "Notification")[:500],
                message=message.body[:20_000],
                severity=message.severity,
                related_entity_type=message.related_entity_type,
                related_entity_id=message.related_entity_id,
                action_url=_internal_action_url(message.action_url),
            )
        )
        return DeliveryResult(
            succeeded=True,
            delivered=True,
            provider_message_id=str(notification.id),
        )
