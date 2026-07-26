"""Administrative notification delivery history queries."""

from __future__ import annotations

from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.schemas.notification import (
    NotificationDeliveryListResponse,
    NotificationDeliveryResponse,
)


class NotificationDeliveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = NotificationDeliveryRepository(session)

    async def list(
        self,
        *,
        status: NotificationDeliveryStatus | None,
        event_type: NotificationEventType | None,
        channel: NotificationChannel | None,
        page: int,
        page_size: int,
    ) -> NotificationDeliveryListResponse:
        rows, total = await self.repository.list_page(
            status=status,
            event_type=event_type,
            channel=channel,
            page=page,
            page_size=page_size,
        )
        return NotificationDeliveryListResponse(
            items=[NotificationDeliveryResponse.model_validate(row) for row in rows],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )
