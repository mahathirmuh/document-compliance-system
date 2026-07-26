"""Auditable, retry-safe delivery through channel adapters."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_enums import (
    TERMINAL_NOTIFICATION_DELIVERY_STATUSES,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
    NotificationChannelError,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)
from app.utils.datetime import utc_now

_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,99}$")


class NotificationDispatchService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        channels: Mapping[NotificationChannel, BaseNotificationChannel],
        maximum_attempts: int = 3,
        retry_base_seconds: int = 60,
    ) -> None:
        self.session = session
        self.channels = dict(channels)
        self.maximum_attempts = max(1, min(maximum_attempts, 20))
        self.retry_base_seconds = max(1, retry_base_seconds)
        self.deliveries = NotificationDeliveryRepository(session)
        self.audit = AuditLogRepository(session)

    async def dispatch(
        self,
        message: NotificationMessage,
        *,
        template_id: UUID | None,
        request_id: str | None = None,
    ) -> NotificationDelivery:
        delivery = NotificationDelivery(
            event_type=message.event_type,
            channel=message.channel,
            template_id=template_id,
            recipient_type=message.recipient.recipient_type,
            recipient_reference=message.recipient.reference[:1000],
            subject=message.subject,
            payload_hash=self.payload_hash(message),
            status=NotificationDeliveryStatus.SENDING,
            attempt_count=1,
            maximum_attempts=self.maximum_attempts,
            metadata_json={
                "requestId": request_id,
                "relatedEntityType": message.related_entity_type,
                "relatedEntityId": (
                    str(message.related_entity_id)
                    if message.related_entity_id
                    else None
                ),
            },
        )
        await self.deliveries.add(delivery)
        result = await self._send(message, request_id=request_id)
        self._apply_result(delivery, result)
        await self._audit_delivery(delivery)
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery

    async def retry_existing(
        self,
        delivery_id: UUID,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> NotificationDelivery:
        delivery = await self.deliveries.get_by_id(
            delivery_id,
            for_update=True,
        )
        if delivery is None:
            raise ValueError("Notification delivery was not found.")
        if delivery.status in TERMINAL_NOTIFICATION_DELIVERY_STATUSES:
            return delivery
        if delivery.payload_hash != self.payload_hash(message):
            raise ValueError("Retry payload does not match the original delivery.")
        if delivery.attempt_count >= delivery.maximum_attempts:
            delivery.status = NotificationDeliveryStatus.FAILED
            delivery.next_retry_at = None
            delivery.error_code = "NOTIFICATION_RETRY_EXHAUSTED"
            delivery.error_message = (
                "Notification delivery exhausted its configured retries."
            )
            await self.session.commit()
            return delivery
        delivery.status = NotificationDeliveryStatus.SENDING
        delivery.attempt_count += 1
        delivery.next_retry_at = None
        result = await self._send(message, request_id=request_id)
        self._apply_result(delivery, result)
        await self._audit_delivery(delivery)
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery

    async def _send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None,
    ) -> DeliveryResult:
        channel = self.channels.get(message.channel)
        if channel is None:
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_CHANNEL_DISABLED",
                error_message="Notification channel is not configured.",
                retryable=False,
            )
        try:
            return await channel.send(message, request_id=request_id)
        except NotificationChannelError as exc:
            return DeliveryResult(
                succeeded=False,
                error_code=exc.code,
                error_message=exc.safe_message,
                retryable=exc.retryable,
            )
        except Exception:  # noqa: BLE001 - provider boundary is untrusted
            return DeliveryResult(
                succeeded=False,
                error_code="NOTIFICATION_DELIVERY_FAILED",
                error_message="Notification provider returned an unexpected failure.",
                retryable=True,
            )

    def _apply_result(
        self,
        delivery: NotificationDelivery,
        result: DeliveryResult,
    ) -> None:
        now = utc_now()
        if result.succeeded:
            delivery.status = (
                NotificationDeliveryStatus.DELIVERED
                if result.delivered
                else NotificationDeliveryStatus.SENT
            )
            delivery.provider_message_id = (
                result.provider_message_id[:1000]
                if result.provider_message_id
                else None
            )
            delivery.sent_at = now
            delivery.delivered_at = now if result.delivered else None
            delivery.error_code = None
            delivery.error_message = None
            delivery.next_retry_at = None
            return
        delivery.failed_at = now
        delivery.error_code = self._safe_error_code(result.error_code)
        delivery.error_message = (result.error_message or "Delivery failed.")[:1000]
        if result.retryable and delivery.attempt_count < delivery.maximum_attempts:
            delivery.status = NotificationDeliveryStatus.RETRY_SCHEDULED
            delay = self.retry_base_seconds * (2 ** (delivery.attempt_count - 1))
            delivery.next_retry_at = now + timedelta(seconds=delay)
        else:
            delivery.status = NotificationDeliveryStatus.FAILED
            delivery.next_retry_at = None
            if result.retryable:
                delivery.error_code = "NOTIFICATION_RETRY_EXHAUSTED"
                delivery.error_message = (
                    "Notification delivery exhausted its configured retries."
                )

    @staticmethod
    def payload_hash(message: NotificationMessage) -> str:
        canonical = json.dumps(
            {
                "eventType": message.event_type.value,
                "channel": message.channel.value,
                "recipientType": message.recipient.recipient_type.value,
                "recipientReference": message.recipient.reference,
                "subject": message.subject,
                "body": message.body,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_error_code(value: str | None) -> str:
        if value and _SAFE_ERROR_CODE.fullmatch(value):
            return value
        return "NOTIFICATION_DELIVERY_FAILED"

    async def _audit_delivery(
        self,
        delivery: NotificationDelivery,
    ) -> None:
        succeeded = delivery.status in {
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.DELIVERED,
        }
        await self.audit.create(
            action=(
                AuditAction.SEND_NOTIFICATION
                if succeeded
                else AuditAction.FAIL_NOTIFICATION
            ),
            entity_type="NotificationDelivery",
            entity_id=delivery.id,
            description=(
                "Notification delivered successfully."
                if succeeded
                else "Notification delivery failed or was deferred."
            ),
            new_values={
                "eventType": delivery.event_type.value,
                "channel": delivery.channel.value,
                "status": delivery.status.value,
                "attemptCount": delivery.attempt_count,
                "errorCode": delivery.error_code,
            },
        )
