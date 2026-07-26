"""Resolve recipients from trusted identifiers and active database users."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import UserRole
from app.models.notification_enums import (
    NotificationChannel,
    NotificationRecipientType,
)
from app.models.notification_rule import NotificationRule
from app.models.user import User
from app.services.notification.contracts import (
    NotificationEvent,
    ResolvedRecipient,
)

_MAX_RESOLVED_RECIPIENTS = 1000


class NotificationRecipientService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self,
        rule: NotificationRule,
        event: NotificationEvent,
    ) -> list[ResolvedRecipient]:
        recipient_type = rule.recipient_type
        if recipient_type == NotificationRecipientType.SPECIFIC_EMAILS:
            return self._direct_recipients(
                recipient_type,
                self._configured(rule, "emails"),
            )
        if recipient_type == NotificationRecipientType.TEAMS_CHANNEL:
            return self._direct_recipients(
                recipient_type,
                self._configured(rule, "channelIds"),
            )
        if recipient_type == NotificationRecipientType.TELEGRAM_CHAT:
            return self._direct_recipients(
                recipient_type,
                self._configured(rule, "chatIds"),
            )

        users = await self._resolve_users(rule, event)
        recipients: list[ResolvedRecipient] = []
        for user in users:
            reference = self._user_reference(user, rule.channel)
            if reference is None:
                continue
            recipients.append(
                ResolvedRecipient(
                    recipient_type=recipient_type,
                    reference=reference,
                    user_id=user.id,
                )
            )
        return recipients

    async def _resolve_users(
        self,
        rule: NotificationRule,
        event: NotificationEvent,
    ) -> list[User]:
        recipient_type = rule.recipient_type
        user_ids: list[UUID] = []
        roles: list[UserRole] = []
        department_id: UUID | None = None
        if recipient_type == NotificationRecipientType.EVENT_ACTOR:
            user_ids = [event.actor_id] if event.actor_id else []
        elif recipient_type == NotificationRecipientType.SPECIFIC_USERS:
            user_ids = self._uuid_values(self._configured(rule, "userIds"))
        elif recipient_type == NotificationRecipientType.DOCUMENT_CONTROLLER:
            roles = [UserRole.DOCUMENT_CONTROLLER]
            department_id = rule.department_id or event.department_id
        elif recipient_type == NotificationRecipientType.DEPARTMENT_USERS:
            department_id = rule.department_id or event.department_id
            if department_id is None:
                return []
        elif recipient_type == NotificationRecipientType.ROLE:
            for item in self._configured(rule, "roles"):
                try:
                    roles.append(UserRole(item))
                except ValueError:
                    continue
            department_id = rule.department_id or event.department_id
        else:
            user_ids = self._uuid_values(
                event.recipient_context.get(recipient_type.value, ())
            )
        if not user_ids and not roles and department_id is None:
            return []
        statement = (
            select(User)
            .where(
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(User.id.asc())
            .limit(_MAX_RESOLVED_RECIPIENTS)
        )
        if user_ids:
            statement = statement.where(User.id.in_(user_ids))
        if roles:
            statement = statement.where(User.role.in_(roles))
        if department_id is not None:
            statement = statement.where(User.department_id == department_id)
        return list(await self.session.scalars(statement))

    @staticmethod
    def _user_reference(
        user: User,
        channel: NotificationChannel,
    ) -> str | None:
        if channel == NotificationChannel.IN_APP:
            return str(user.id)
        if channel == NotificationChannel.EMAIL_GRAPH:
            return user.email
        return None

    @staticmethod
    def _direct_recipients(
        recipient_type: NotificationRecipientType,
        values: Sequence[str],
    ) -> list[ResolvedRecipient]:
        result: list[ResolvedRecipient] = []
        seen: set[str] = set()
        for raw_reference in values[:_MAX_RESOLVED_RECIPIENTS]:
            reference = str(raw_reference).strip()
            normalized = reference.casefold()
            if not reference or len(reference) > 1000 or normalized in seen:
                continue
            seen.add(normalized)
            result.append(
                ResolvedRecipient(
                    recipient_type=recipient_type,
                    reference=reference,
                )
            )
        return result

    @staticmethod
    def _configured(rule: NotificationRule, key: str) -> list[str]:
        values = rule.recipient_value_json.get(key, [])
        if not isinstance(values, list):
            return []
        return [str(value) for value in values]

    @staticmethod
    def _uuid_values(values: Sequence[str]) -> list[UUID]:
        result: list[UUID] = []
        for value in values:
            try:
                result.append(UUID(str(value)))
            except (TypeError, ValueError):
                continue
        return list(dict.fromkeys(result))
