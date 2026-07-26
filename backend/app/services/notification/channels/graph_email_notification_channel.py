"""Microsoft Graph mail adapter with a fixed configured sender."""

from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any, Protocol

from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
)
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
    NotificationChannelError,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)

_EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,63}$",
    re.IGNORECASE,
)


class GraphMailClient(Protocol):
    async def send_mail(
        self,
        *,
        sender_user_id: str,
        message: dict[str, Any],
        client_request_id: str | None,
    ) -> str | None: ...


def validate_email_address(value: str) -> str:
    candidate = value.strip()
    _, parsed = parseaddr(candidate)
    if (
        parsed != candidate
        or len(candidate) > 320
        or not _EMAIL_PATTERN.fullmatch(candidate)
    ):
        raise NotificationChannelError(
            "NOTIFICATION_RECIPIENT_NOT_FOUND",
            "Email recipient is invalid.",
            retryable=False,
        )
    return candidate


class GraphEmailNotificationChannel(BaseNotificationChannel):
    channel = NotificationChannel.EMAIL_GRAPH

    def __init__(
        self,
        client: GraphMailClient,
        *,
        enabled: bool,
        sender_user_id: str,
        reply_to: str | None = None,
        maximum_recipients: int = 100,
    ) -> None:
        if maximum_recipients < 1 or maximum_recipients > 500:
            raise ValueError("maximum_recipients must be between 1 and 500.")
        self.client = client
        self.enabled = enabled
        self.sender_user_id = sender_user_id.strip()
        self.reply_to = validate_email_address(reply_to) if reply_to else None
        self.maximum_recipients = maximum_recipients

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
                error_message="Graph email notification is disabled.",
                retryable=False,
            )
        if not self.sender_user_id:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_CHANNEL_DISABLED",
                error_message="Graph email sender is not configured.",
                retryable=False,
            )
        recipients = [
            validate_email_address(value)
            for value in message.recipient.reference.split(",")
            if value.strip()
        ]
        if not recipients or len(recipients) > self.maximum_recipients:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_RECIPIENT_NOT_FOUND",
                error_message="Email recipient count is outside the allowed range.",
                retryable=False,
            )
        subject = (
            (message.subject or "Notification")
            .replace("\r", " ")
            .replace("\n", " ")[:500]
        )
        content_type = (
            "HTML" if message.content_type == NotificationContentType.HTML else "Text"
        )
        graph_message: dict[str, Any] = {
            "subject": subject,
            "body": {
                "contentType": content_type,
                "content": message.body[:100_000],
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient}} for recipient in recipients
            ],
        }
        if self.reply_to:
            graph_message["replyTo"] = [{"emailAddress": {"address": self.reply_to}}]
        try:
            provider_id = await self.client.send_mail(
                sender_user_id=self.sender_user_id,
                message=graph_message,
                client_request_id=request_id,
            )
        except NotificationChannelError:
            raise
        except Exception as exc:
            raise NotificationChannelError(
                "NOTIFICATION_EMAIL_SEND_FAILED",
                "Microsoft Graph mail provider is unavailable.",
                retryable=True,
            ) from exc
        return DeliveryResult(
            succeeded=True,
            provider_message_id=provider_id,
        )
