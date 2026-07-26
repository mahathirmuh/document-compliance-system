"""Notification delivery history and retry queue queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_delivery import NotificationDelivery
from app.models.notification_enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)


class NotificationDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        delivery: NotificationDelivery,
    ) -> NotificationDelivery:
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def get_by_id(
        self,
        delivery_id: UUID,
        *,
        for_update: bool = False,
    ) -> NotificationDelivery | None:
        statement = select(NotificationDelivery).where(
            NotificationDelivery.id == delivery_id
        )
        if for_update:
            statement = statement.with_for_update(of=NotificationDelivery)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        status: NotificationDeliveryStatus | None,
        event_type: NotificationEventType | None,
        channel: NotificationChannel | None,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationDelivery], int]:
        predicates = []
        if status is not None:
            predicates.append(NotificationDelivery.status == status)
        if event_type is not None:
            predicates.append(NotificationDelivery.event_type == event_type)
        if channel is not None:
            predicates.append(NotificationDelivery.channel == channel)
        base = select(NotificationDelivery).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(NotificationDelivery.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def due_retries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[NotificationDelivery]:
        statement = (
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status
                == NotificationDeliveryStatus.RETRY_SCHEDULED,
                NotificationDelivery.next_retry_at <= now,
                NotificationDelivery.attempt_count
                < NotificationDelivery.maximum_attempts,
            )
            .order_by(NotificationDelivery.next_retry_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(await self.session.scalars(statement))
