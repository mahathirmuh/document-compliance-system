"""Persistence queries for versioned notification templates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_enums import (
    NotificationChannel,
    NotificationEventType,
)
from app.models.notification_template import NotificationTemplate


class NotificationTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, template: NotificationTemplate) -> NotificationTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_by_id(
        self,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> NotificationTemplate | None:
        statement = select(NotificationTemplate).where(
            NotificationTemplate.id == template_id
        )
        if for_update:
            statement = statement.with_for_update(of=NotificationTemplate)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        event_type: NotificationEventType | None = None,
        channel: NotificationChannel | None = None,
        include_inactive: bool = False,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationTemplate], int]:
        predicates = []
        if event_type is not None:
            predicates.append(NotificationTemplate.event_type == event_type)
        if channel is not None:
            predicates.append(NotificationTemplate.channel == channel)
        if not include_inactive:
            predicates.append(NotificationTemplate.is_active.is_(True))
        base = select(NotificationTemplate).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(
                NotificationTemplate.code.asc(),
                NotificationTemplate.version.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def resolve(
        self,
        *,
        event_type: NotificationEventType,
        channel: NotificationChannel,
        language_code: str,
    ) -> NotificationTemplate | None:
        statement = (
            select(NotificationTemplate)
            .where(
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.channel == channel,
                NotificationTemplate.language_code.in_(
                    (language_code.casefold(), "en")
                ),
                NotificationTemplate.is_active.is_(True),
            )
            .order_by(
                (NotificationTemplate.language_code == language_code.casefold()).desc(),
                NotificationTemplate.is_default.desc(),
                NotificationTemplate.version.desc(),
            )
            .limit(1)
        )
        return await self.session.scalar(statement)
