"""Telegram adapter whose injected client owns the bot credential."""

from __future__ import annotations

from typing import Protocol

from app.models.notification_enums import NotificationChannel
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
    NotificationChannelError,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)


class TelegramClient(Protocol):
    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
    ) -> str | None: ...


class TelegramNotificationChannel(BaseNotificationChannel):
    channel = NotificationChannel.TELEGRAM

    def __init__(
        self,
        client: TelegramClient,
        *,
        enabled: bool,
        default_chat_id: str | None,
    ) -> None:
        self.client = client
        self.enabled = enabled
        self.default_chat_id = default_chat_id

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
                error_message="Telegram notifications are disabled.",
                retryable=False,
            )
        chat_id = message.recipient.reference or self.default_chat_id
        if not chat_id or len(chat_id) > 100:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_RECIPIENT_NOT_FOUND",
                error_message="Telegram chat recipient is invalid.",
                retryable=False,
            )
        text = "\n\n".join(
            item
            for item in ((message.subject or "")[:500], message.body[:3500])
            if item
        )
        try:
            provider_id = await self.client.send_message(
                chat_id=chat_id,
                text=text,
            )
        except Exception as exc:
            raise NotificationChannelError(
                "NOTIFICATION_TELEGRAM_SEND_FAILED",
                "Telegram notification provider is unavailable.",
                retryable=True,
            ) from exc
        return DeliveryResult(
            succeeded=True,
            provider_message_id=provider_id,
        )
