"""Dead-letter task administration queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter_job import DeadLetterJob, DeadLetterStatus


class DeadLetterJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: DeadLetterJob) -> DeadLetterJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> DeadLetterJob | None:
        statement = select(DeadLetterJob).where(DeadLetterJob.id == job_id)
        if for_update:
            statement = statement.with_for_update(of=DeadLetterJob)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        status: DeadLetterStatus | None,
        task_name: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[DeadLetterJob], int]:
        predicates = []
        if status is not None:
            predicates.append(DeadLetterJob.status == status)
        if task_name:
            predicates.append(DeadLetterJob.task_name == task_name)
        base = select(DeadLetterJob).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(DeadLetterJob.last_failed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total
