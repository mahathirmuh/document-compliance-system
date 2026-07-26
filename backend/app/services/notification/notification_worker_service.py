"""Worker runtime for strict notification queue payloads."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import AsyncSessionFactory
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
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.channels.in_app_notification_channel import (
    InAppNotificationChannel,
)
from app.services.notification.notification_dispatch_service import (
    NotificationDispatchService,
)
from app.utils.datetime import utc_now

NotificationChannelFactory = Callable[
    [AsyncSession],
    Mapping[NotificationChannel, BaseNotificationChannel],
]


class NotificationRetryMessageResolver(Protocol):
    async def resolve(
        self,
        *,
        session: AsyncSession,
        delivery_id: UUID,
    ) -> NotificationTaskPayload: ...


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
        maximum_attempts: int = 3,
    ) -> None:
        self.session_factory = session_factory
        self.channel_factory = channel_factory
        self.retry_message_resolver = retry_message_resolver
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
