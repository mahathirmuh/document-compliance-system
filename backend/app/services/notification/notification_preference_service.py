"""Per-user channel, digest, and timezone-aware quiet-hour policy."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_enums import (
    SYSTEM_CRITICAL_NOTIFICATION_EVENTS,
    NotificationChannel,
    NotificationEventType,
)
from app.models.notification_preference import NotificationPreference
from app.repositories.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from app.schemas.notification import (
    NotificationPreferenceResponse,
    NotificationPreferencesUpdateRequest,
)


class NotificationPreferenceService:
    def __init__(self, session: AsyncSession, *, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repository = NotificationPreferenceRepository(session)

    async def list(self) -> list[NotificationPreferenceResponse]:
        stored = {
            item.event_type: item
            for item in await self.repository.list_for_user(self.user_id)
        }
        return [
            (
                NotificationPreferenceResponse.model_validate(stored[event_type])
                if event_type in stored
                else NotificationPreferenceResponse(
                    id=None,
                    user_id=self.user_id,
                    event_type=event_type,
                    created_at=None,
                    updated_at=None,
                )
            )
            for event_type in NotificationEventType
        ]

    async def update(
        self,
        payload: NotificationPreferencesUpdateRequest,
    ) -> list[NotificationPreferenceResponse]:
        results: list[NotificationPreference] = []
        for item in payload.preferences:
            preference = await self.repository.get_for_user_event(
                user_id=self.user_id,
                event_type=item.event_type,
                for_update=True,
            )
            values = item.model_dump()
            if preference is None:
                preference = NotificationPreference(
                    user_id=self.user_id,
                    **values,
                )
                await self.repository.add(preference)
            else:
                for field, value in values.items():
                    if field != "event_type":
                        setattr(preference, field, value)
            results.append(preference)
        await self.session.commit()
        for preference in results:
            await self.session.refresh(preference)
        return await self.list()

    async def delivery_allowed(
        self,
        *,
        event_type: NotificationEventType,
        channel: NotificationChannel,
        mandatory_rule: bool,
        now: datetime,
    ) -> bool:
        if mandatory_rule and event_type in SYSTEM_CRITICAL_NOTIFICATION_EVENTS:
            return True
        preference = await self.repository.get_for_user_event(
            user_id=self.user_id,
            event_type=event_type,
        )
        if preference is None:
            return channel == NotificationChannel.IN_APP
        enabled = {
            NotificationChannel.IN_APP: preference.in_app_enabled,
            NotificationChannel.EMAIL_GRAPH: preference.email_enabled,
            NotificationChannel.TEAMS: preference.teams_enabled,
            NotificationChannel.TELEGRAM: preference.telegram_enabled,
        }[channel]
        if not enabled or not preference.quiet_hours_enabled:
            return enabled
        if preference.quiet_hours_start is None or preference.quiet_hours_end is None:
            return enabled
        local_time = now.astimezone(ZoneInfo(preference.timezone)).time()
        start = preference.quiet_hours_start
        end = preference.quiet_hours_end
        in_quiet_hours = (
            start <= local_time < end
            if start < end
            else local_time >= start or local_time < end
        )
        return not in_quiet_hours
