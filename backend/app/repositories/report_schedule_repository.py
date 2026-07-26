"""Database-only operations for manual report schedules."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.report_schedule import ReportSchedule


class ReportScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, schedule: ReportSchedule) -> ReportSchedule:
        self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def get_by_id(
        self,
        schedule_id: UUID,
        *,
        department_ids: Sequence[UUID] | None,
        for_update: bool = False,
    ) -> ReportSchedule | None:
        predicates: list[ColumnElement[bool]] = [ReportSchedule.id == schedule_id]
        if department_ids is not None:
            if not department_ids:
                return None
            predicates.append(
                ReportSchedule.scope_department_id.in_(department_ids)
            )
        statement = select(ReportSchedule).where(*predicates)
        if for_update:
            statement = statement.with_for_update(of=ReportSchedule)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[ReportSchedule], int]:
        predicates: list[ColumnElement[bool]] = []
        if department_ids is not None:
            if not department_ids:
                return [], 0
            predicates.append(
                ReportSchedule.scope_department_id.in_(department_ids)
            )
        if not include_inactive:
            predicates.append(ReportSchedule.is_active.is_(True))
        base = select(ReportSchedule).where(*predicates)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                ReportSchedule.created_at.desc(),
                ReportSchedule.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total
