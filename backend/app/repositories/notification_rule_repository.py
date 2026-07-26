"""Persistence queries for scoped notification rules."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_enums import (
    NotificationChannel,
    NotificationEventType,
    NotificationScopeType,
)
from app.models.notification_rule import NotificationRule


class NotificationRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rule: NotificationRule) -> NotificationRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_by_id(
        self,
        rule_id: UUID,
        *,
        for_update: bool = False,
    ) -> NotificationRule | None:
        statement = select(NotificationRule).where(NotificationRule.id == rule_id)
        if for_update:
            statement = statement.with_for_update(of=NotificationRule)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        event_type: NotificationEventType | None = None,
        channel: NotificationChannel | None = None,
        include_inactive: bool = False,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationRule], int]:
        predicates = []
        if event_type is not None:
            predicates.append(NotificationRule.event_type == event_type)
        if channel is not None:
            predicates.append(NotificationRule.channel == channel)
        if not include_inactive:
            predicates.append(NotificationRule.is_active.is_(True))
        base = select(NotificationRule).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(NotificationRule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def matching_rules(
        self,
        *,
        event_type: NotificationEventType,
        department_id: UUID | None,
        document_type_id: UUID | None,
    ) -> list[NotificationRule]:
        scope_predicates = [NotificationRule.scope_type == NotificationScopeType.GLOBAL]
        if department_id is not None:
            scope_predicates.append(
                and_(
                    NotificationRule.scope_type == NotificationScopeType.DEPARTMENT,
                    NotificationRule.department_id == department_id,
                )
            )
        if document_type_id is not None:
            scope_predicates.append(
                and_(
                    NotificationRule.scope_type == NotificationScopeType.DOCUMENT_TYPE,
                    NotificationRule.document_type_id == document_type_id,
                )
            )
        if department_id is not None and document_type_id is not None:
            scope_predicates.append(
                and_(
                    NotificationRule.scope_type
                    == NotificationScopeType.DEPARTMENT_DOCUMENT_TYPE,
                    NotificationRule.department_id == department_id,
                    NotificationRule.document_type_id == document_type_id,
                )
            )
        statement = (
            select(NotificationRule)
            .where(
                NotificationRule.event_type == event_type,
                NotificationRule.is_active.is_(True),
                or_(*scope_predicates),
            )
            .order_by(NotificationRule.created_at.asc())
        )
        return list(await self.session.scalars(statement))
