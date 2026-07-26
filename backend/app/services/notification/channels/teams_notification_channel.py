"""Bounded Microsoft Teams webhook notification adapter."""

from __future__ import annotations

from typing import Any, Protocol

from app.models.notification_enums import NotificationChannel
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
    NotificationChannelError,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)


class TeamsWebhookClient(Protocol):
    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> str | None: ...


class TeamsNotificationChannel(BaseNotificationChannel):
    channel = NotificationChannel.TEAMS

    def __init__(
        self,
        client: TeamsWebhookClient,
        *,
        enabled: bool,
        mode: str,
        webhook_url: str,
        timeout_seconds: float = 10,
    ) -> None:
        self.client = client
        self.enabled = enabled
        self.mode = mode.strip().upper()
        self._webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    async def send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> DeliveryResult:
        if not self.enabled:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_CHANNEL_DISABLED",
                error_message="Teams notifications are disabled.",
                retryable=False,
            )
        if self.mode not in {"INCOMING_WEBHOOK", "WORKFLOW_WEBHOOK"}:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_CHANNEL_DISABLED",
                error_message="Configured Teams mode is unsupported by this adapter.",
                retryable=False,
            )
        if not self._webhook_url.lower().startswith("https://"):
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_CHANNEL_DISABLED",
                error_message="Teams webhook is not securely configured.",
                retryable=False,
            )
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "weight": "Bolder",
                                "wrap": True,
                                "text": (message.subject or "Notification")[:500],
                            },
                            {
                                "type": "TextBlock",
                                "wrap": True,
                                "text": message.body[:5000],
                            },
                        ],
                    },
                }
            ],
        }
        try:
            provider_id = await self.client.post_json(
                url=self._webhook_url,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            raise NotificationChannelError(
                "NOTIFICATION_TEAMS_SEND_FAILED",
                "Microsoft Teams notification provider is unavailable.",
                retryable=True,
            ) from exc
        return DeliveryResult(
            succeeded=True,
            provider_message_id=provider_id,
        )
