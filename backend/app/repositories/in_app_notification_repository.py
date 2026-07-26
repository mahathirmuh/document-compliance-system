"""Strictly user-scoped in-app notification queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.in_app_notification import InAppNotification


class InAppNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        notification: InAppNotification,
    ) -> InAppNotification:
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_for_user(
        self,
        *,
        notification_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> InAppNotification | None:
        statement = select(InAppNotification).where(
            InAppNotification.id == notification_id,
            InAppNotification.user_id == user_id,
            InAppNotification.dismissed_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update(of=InAppNotification)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        user_id: UUID,
        unread_only: bool,
        now: datetime,
        page: int,
        page_size: int,
    ) -> tuple[list[InAppNotification], int]:
        predicates = [
            InAppNotification.user_id == user_id,
            InAppNotification.dismissed_at.is_(None),
            (
                InAppNotification.expires_at.is_(None)
                | (InAppNotification.expires_at > now)
            ),
        ]
        if unread_only:
            predicates.append(InAppNotification.is_read.is_(False))
        base = select(InAppNotification).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(
                InAppNotification.created_at.desc(),
                InAppNotification.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def unread_count(self, *, user_id: UUID, now: datetime) -> int:
        statement = (
            select(func.count())
            .select_from(InAppNotification)
            .where(
                InAppNotification.user_id == user_id,
                InAppNotification.is_read.is_(False),
                InAppNotification.dismissed_at.is_(None),
                (
                    InAppNotification.expires_at.is_(None)
                    | (InAppNotification.expires_at > now)
                ),
            )
        )
        return int(await self.session.scalar(statement) or 0)

    async def mark_all_read(
        self,
        *,
        user_id: UUID,
        read_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(InAppNotification)
            .where(
                InAppNotification.user_id == user_id,
                InAppNotification.is_read.is_(False),
                InAppNotification.dismissed_at.is_(None),
            )
            .values(is_read=True, read_at=read_at)
        )
        return int(result.rowcount or 0)

    async def delete_expired(self, *, now: datetime, batch_size: int) -> int:
        ids = list(
            await self.session.scalars(
                select(InAppNotification.id)
                .where(InAppNotification.expires_at <= now)
                .order_by(InAppNotification.expires_at.asc())
                .limit(batch_size)
            )
        )
        if not ids:
            return 0
        result = await self.session.execute(
            delete(InAppNotification).where(InAppNotification.id.in_(ids))
        )
        return int(result.rowcount or 0)
