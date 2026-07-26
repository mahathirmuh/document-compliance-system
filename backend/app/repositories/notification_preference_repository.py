"""User-owned notification preference queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_enums import NotificationEventType
from app.models.notification_preference import NotificationPreference


class NotificationPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        preference: NotificationPreference,
    ) -> NotificationPreference:
        self.session.add(preference)
        await self.session.flush()
        return preference

    async def list_for_user(self, user_id: UUID) -> list[NotificationPreference]:
        statement = (
            select(NotificationPreference)
            .where(NotificationPreference.user_id == user_id)
            .order_by(NotificationPreference.event_type.asc())
        )
        return list(await self.session.scalars(statement))

    async def get_for_user_event(
        self,
        *,
        user_id: UUID,
        event_type: NotificationEventType,
        for_update: bool = False,
    ) -> NotificationPreference | None:
        statement = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        )
        if for_update:
            statement = statement.with_for_update(of=NotificationPreference)
        return await self.session.scalar(statement)
