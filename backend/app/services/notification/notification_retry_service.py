"""Bounded manual and scheduled notification retry controls."""

from __future__ import annotations

from http import HTTPStatus
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_enums import NotificationDeliveryStatus
from app.repositories.audit_log import AuditLogRepository
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.schemas.notification import NotificationRetryResponse
from app.services.notification.errors import notification_error
from app.utils.datetime import utc_now


class NotificationRetryPublisher(Protocol):
    async def publish(self, *, delivery_id: UUID) -> str | None: ...


class NotificationRetryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        publisher: NotificationRetryPublisher | None = None,
        actor_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.repository = NotificationDeliveryRepository(session)
        self.publisher = publisher
        self.actor_id = actor_id
        self.audit = AuditLogRepository(session)

    async def queue_manual_retry(
        self,
        delivery_id: UUID,
    ) -> NotificationRetryResponse:
        delivery = await self._get(delivery_id, for_update=True)
        if delivery.status not in {
            NotificationDeliveryStatus.FAILED,
            NotificationDeliveryStatus.RETRY_SCHEDULED,
        }:
            raise notification_error(
                "Only failed notification deliveries can be retried.",
                code="NOTIFICATION_DELIVERY_NOT_RETRYABLE",
                status_code=HTTPStatus.CONFLICT,
            )
        if self.publisher is None:
            raise notification_error(
                "Notification retry queue is not configured.",
                code="NOTIFICATION_RETRY_QUEUE_UNAVAILABLE",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        if delivery.attempt_count >= delivery.maximum_attempts:
            delivery.maximum_attempts = delivery.attempt_count + 1
        metadata = dict(delivery.metadata_json)
        metadata["manualRetryCount"] = int(metadata.get("manualRetryCount", 0)) + 1
        delivery.metadata_json = metadata
        delivery.status = NotificationDeliveryStatus.RETRY_SCHEDULED
        delivery.next_retry_at = utc_now()
        delivery.error_code = None
        delivery.error_message = None
        try:
            provider_task_id = await self.publisher.publish(delivery_id=delivery.id)
        except Exception as exc:
            raise notification_error(
                "Notification retry could not be queued.",
                code="NOTIFICATION_RETRY_QUEUE_UNAVAILABLE",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc
        if provider_task_id:
            metadata["retryTaskId"] = provider_task_id
            delivery.metadata_json = metadata
        await self.audit.create(
            action=AuditAction.RETRY_NOTIFICATION,
            user_id=self.actor_id,
            entity_type="NotificationDelivery",
            entity_id=delivery.id,
            description="Notification delivery retry queued.",
            new_values={
                "status": delivery.status.value,
                "attemptCount": delivery.attempt_count,
                "maximumAttempts": delivery.maximum_attempts,
            },
        )
        await self.session.commit()
        return NotificationRetryResponse(
            delivery_id=delivery.id,
            status=delivery.status,
        )

    async def due(self, *, limit: int = 100) -> list[NotificationDelivery]:
        return await self.repository.due_retries(
            now=utc_now(),
            limit=max(1, min(limit, 1000)),
        )

    async def _get(
        self,
        delivery_id: UUID,
        *,
        for_update: bool,
    ) -> NotificationDelivery:
        delivery = await self.repository.get_by_id(
            delivery_id,
            for_update=for_update,
        )
        if delivery is None:
            raise notification_error(
                "Notification delivery was not found.",
                code="NOTIFICATION_DELIVERY_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return delivery
