"""Graph subscription and webhook event persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph_subscription import GraphSubscription
from app.models.graph_webhook_event import GraphWebhookEvent
from app.models.sharepoint_enums import GraphSubscriptionStatus


class GraphSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        subscription: GraphSubscription,
    ) -> GraphSubscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_id(
        self,
        subscription_id: UUID,
        *,
        for_update: bool = False,
    ) -> GraphSubscription | None:
        statement = select(GraphSubscription).where(
            GraphSubscription.id == subscription_id
        )
        if for_update:
            statement = statement.with_for_update(of=GraphSubscription)
        return await self.session.scalar(statement)

    async def get_by_remote_id(
        self,
        subscription_id: str,
        *,
        for_update: bool = False,
    ) -> GraphSubscription | None:
        statement = select(GraphSubscription).where(
            GraphSubscription.subscription_id == subscription_id
        )
        if for_update:
            statement = statement.with_for_update(of=GraphSubscription)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        statuses: list[GraphSubscriptionStatus] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[GraphSubscription], int]:
        base = select(GraphSubscription)
        if statuses:
            base = base.where(GraphSubscription.status.in_(statuses))
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(GraphSubscription.expiration_datetime.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def expiring_before(
        self,
        deadline: datetime,
    ) -> list[GraphSubscription]:
        return list(
            await self.session.scalars(
                select(GraphSubscription).where(
                    GraphSubscription.status.in_(
                        (
                            GraphSubscriptionStatus.ACTIVE,
                            GraphSubscriptionStatus.EXPIRING,
                            GraphSubscriptionStatus.RENEWAL_FAILED,
                        )
                    ),
                    GraphSubscription.expiration_datetime <= deadline,
                )
            )
        )

    async def add_event(
        self,
        event: GraphWebhookEvent,
    ) -> GraphWebhookEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event_by_payload(
        self,
        *,
        subscription_id: str,
        payload_hash: str,
    ) -> GraphWebhookEvent | None:
        return await self.session.scalar(
            select(GraphWebhookEvent).where(
                GraphWebhookEvent.subscription_id == subscription_id,
                GraphWebhookEvent.payload_hash == payload_hash,
            )
        )

    async def get_event(
        self,
        event_id: UUID,
        *,
        for_update: bool = False,
    ) -> GraphWebhookEvent | None:
        statement = select(GraphWebhookEvent).where(
            GraphWebhookEvent.id == event_id
        )
        if for_update:
            statement = statement.with_for_update(of=GraphWebhookEvent)
        return await self.session.scalar(statement)
