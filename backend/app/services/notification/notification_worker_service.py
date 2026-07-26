"""Worker runtime for strict notification queue payloads."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import AsyncSessionFactory
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.repositories.in_app_notification_repository import (
    InAppNotificationRepository,
)
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.schemas.notification_internal import NotificationTaskPayload
from app.services.maintenance.dead_letter_service import DeadLetterService
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.channels.in_app_notification_channel import (
    InAppNotificationChannel,
)
from app.services.notification.notification_dispatch_service import (
    NotificationDispatchService,
)
from app.utils.datetime import ensure_utc, utc_now

NotificationChannelFactory = Callable[
    [AsyncSession],
    Mapping[NotificationChannel, BaseNotificationChannel],
]
_RETRY_TASK_NAME = "app.workers.notification_tasks.retry_failed_notification"


class NotificationRetryMessageResolver(Protocol):
    async def resolve(
        self,
        *,
        session: AsyncSession,
        delivery_id: UUID,
    ) -> NotificationTaskPayload: ...


class NotificationRetryPayloadStore(NotificationRetryMessageResolver, Protocol):
    async def save(
        self,
        delivery_id: UUID,
        payload: NotificationTaskPayload,
    ) -> None: ...

    async def delete(self, delivery_id: UUID) -> None: ...


class NotificationWorkerRetryPublisher(Protocol):
    async def publish(
        self,
        *,
        delivery_id: UUID,
        delay_seconds: int = 0,
    ) -> str | None: ...


def _default_channel_factory(
    session: AsyncSession,
) -> Mapping[NotificationChannel, BaseNotificationChannel]:
    return {
        NotificationChannel.IN_APP: InAppNotificationChannel(
            InAppNotificationRepository(session)
        )
    }


class NotificationWorkerService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
        channel_factory: NotificationChannelFactory = (_default_channel_factory),
        retry_message_resolver: NotificationRetryMessageResolver | None = None,
        retry_payload_store: NotificationRetryPayloadStore | None = None,
        retry_publisher: NotificationWorkerRetryPublisher | None = None,
        maximum_attempts: int = 3,
    ) -> None:
        self.session_factory = session_factory
        self.channel_factory = channel_factory
        self.retry_message_resolver = retry_message_resolver
        self.retry_payload_store = retry_payload_store
        self.retry_publisher = retry_publisher
        self.maximum_attempts = maximum_attempts

    async def dispatch(
        self,
        raw_payload: Mapping[str, Any],
    ) -> dict[str, str]:
        payload = NotificationTaskPayload.model_validate(raw_payload)
        async with self.session_factory() as session:
            delivery = await NotificationDispatchService(
                session,
                channels=self.channel_factory(session),
                maximum_attempts=self.maximum_attempts,
            ).dispatch(
                payload.to_message(),
                template_id=payload.template_id,
                request_id=payload.request_id,
            )
        await self._schedule_or_clear(delivery, payload)
        return {
            "deliveryId": str(delivery.id),
            "status": delivery.status.value,
        }

    async def retry(
        self,
        delivery_id: UUID,
        raw_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        async with self.session_factory() as session:
            existing = await NotificationDeliveryRepository(session).get_by_id(
                delivery_id
            )
            if existing is None:
                raise ValueError("Notification delivery was not found.")
            if raw_payload is None:
                if self.retry_message_resolver is None:
                    raise RuntimeError(
                        "Notification retry payload resolver is not configured."
                    )
                payload = await self.retry_message_resolver.resolve(
                    session=session,
                    delivery_id=delivery_id,
                )
            else:
                payload = NotificationTaskPayload.model_validate(raw_payload)
            delivery = await NotificationDispatchService(
                session,
                channels=self.channel_factory(session),
                maximum_attempts=self.maximum_attempts,
            ).retry_existing(
                delivery_id,
                payload.to_message(),
                request_id=payload.request_id,
            )
        await self._schedule_or_clear(delivery, payload)
        if delivery.status in {
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.DELIVERED,
        }:
            await self._mark_dead_letter_retried(delivery.id)
        return {
            "deliveryId": str(delivery.id),
            "status": delivery.status.value,
        }

    async def digest(
        self,
        raw_payloads: Sequence[Mapping[str, Any]],
    ) -> dict[str, int]:
        if len(raw_payloads) > 100:
            raise ValueError("A notification digest is limited to 100 items.")
        sent = failed = 0
        for payload in raw_payloads:
            result = await self.dispatch(payload)
            if result["status"] in {
                NotificationDeliveryStatus.SENT.value,
                NotificationDeliveryStatus.DELIVERED.value,
            }:
                sent += 1
            else:
                failed += 1
        return {"sent": sent, "failed": failed}

    async def expire_in_app(self, *, batch_size: int) -> dict[str, int]:
        async with self.session_factory() as session:
            deleted = await InAppNotificationRepository(session).delete_expired(
                now=utc_now(),
                batch_size=max(1, min(batch_size, 5000)),
            )
            await session.commit()
        return {"expired": deleted}

    async def _schedule_or_clear(
        self,
        delivery: NotificationDelivery,
        payload: NotificationTaskPayload,
    ) -> None:
        if delivery.status != NotificationDeliveryStatus.RETRY_SCHEDULED:
            if delivery.status == NotificationDeliveryStatus.FAILED:
                if self.retry_payload_store is not None:
                    try:
                        await self.retry_payload_store.save(
                            delivery.id,
                            payload,
                        )
                    except Exception:  # noqa: BLE001 - manual retry unavailable
                        pass
                if delivery.error_code == "NOTIFICATION_RETRY_EXHAUSTED":
                    try:
                        await self._record_dead_letter(delivery)
                    except Exception:  # noqa: BLE001 - delivery is inspectable
                        pass
                return
            if self.retry_payload_store is not None:
                try:
                    await self.retry_payload_store.delete(delivery.id)
                except Exception:  # noqa: BLE001 - best-effort secret cleanup
                    pass
            return
        if self.retry_payload_store is None or self.retry_publisher is None:
            await self._mark_retry_queue_unavailable(delivery.id)
            delivery.status = NotificationDeliveryStatus.FAILED
            return
        try:
            await self.retry_payload_store.save(delivery.id, payload)
            task_id = await self.retry_publisher.publish(
                delivery_id=delivery.id,
                delay_seconds=self._retry_delay_seconds(delivery.next_retry_at),
            )
        except Exception:  # noqa: BLE001 - Redis/broker boundary is untrusted
            await self._mark_retry_queue_unavailable(delivery.id)
            delivery.status = NotificationDeliveryStatus.FAILED
            return
        if task_id:
            try:
                await self._record_retry_task(delivery.id, task_id)
            except Exception:  # noqa: BLE001 - history is best effort
                pass

    async def _record_retry_task(
        self,
        delivery_id: UUID,
        task_id: str,
    ) -> None:
        async with self.session_factory() as session:
            delivery = await NotificationDeliveryRepository(session).get_by_id(
                delivery_id, for_update=True
            )
            if delivery is None:
                return
            metadata = dict(delivery.metadata_json)
            metadata["retryTaskId"] = task_id[:1000]
            delivery.metadata_json = metadata
            await session.commit()

    async def _record_dead_letter(
        self,
        delivery: NotificationDelivery,
    ) -> None:
        async with self.session_factory() as session:
            await DeadLetterService(session).record(
                task_name=_RETRY_TASK_NAME,
                entity_type="NotificationDelivery",
                entity_id=delivery.id,
                attempts=delivery.attempt_count,
                maximum_attempts=delivery.maximum_attempts,
                arguments={"deliveryId": str(delivery.id)},
                error_code="NOTIFICATION_RETRY_EXHAUSTED",
                safe_error=("Notification delivery exhausted its configured retries."),
            )

    async def _mark_dead_letter_retried(
        self,
        delivery_id: UUID,
    ) -> None:
        async with self.session_factory() as session:
            await DeadLetterService(session).mark_retried_for_entity(
                task_name=_RETRY_TASK_NAME,
                entity_type="NotificationDelivery",
                entity_id=delivery_id,
            )

    async def _mark_retry_queue_unavailable(
        self,
        delivery_id: UUID,
    ) -> None:
        async with self.session_factory() as session:
            delivery = await NotificationDeliveryRepository(session).get_by_id(
                delivery_id, for_update=True
            )
            if delivery is None:
                return
            delivery.status = NotificationDeliveryStatus.FAILED
            delivery.next_retry_at = None
            delivery.error_code = "NOTIFICATION_DELIVERY_FAILED"
            delivery.error_message = "Notification retry could not be queued safely."
            await session.commit()

    @staticmethod
    def _retry_delay_seconds(next_retry_at: datetime | None) -> int:
        if next_retry_at is None:
            return 0
        remaining = (ensure_utc(next_retry_at) - utc_now()).total_seconds()
        return max(0, int(remaining))
