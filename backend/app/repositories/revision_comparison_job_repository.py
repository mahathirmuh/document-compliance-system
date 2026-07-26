"""Database-only operations for revision-comparison jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.document import Document
from app.models.revision_comparison_job import (
    ACTIVE_REVISION_COMPARISON_JOB_STATUSES,
    RevisionComparisonJob,
    RevisionComparisonJobStatus,
)


class RevisionComparisonJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, job: RevisionComparisonJob
    ) -> RevisionComparisonJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> RevisionComparisonJob | None:
        statement = (
            select(RevisionComparisonJob)
            .join(Document, Document.id == RevisionComparisonJob.document_id)
            .where(RevisionComparisonJob.id == job_id)
        )
        if department_ids is not None:
            if not department_ids:
                return None
            statement = statement.where(
                Document.department_id.in_(department_ids)
            )
        if for_update:
            statement = statement.with_for_update(
                of=RevisionComparisonJob
            )
        return await self.session.scalar(statement)

    async def get_active_pair(
        self,
        document_id: UUID,
        base_revision_id: UUID,
        target_revision_id: UUID,
    ) -> RevisionComparisonJob | None:
        return await self.session.scalar(
            select(RevisionComparisonJob).where(
                RevisionComparisonJob.document_id == document_id,
                RevisionComparisonJob.base_revision_id == base_revision_id,
                RevisionComparisonJob.target_revision_id
                == target_revision_id,
                RevisionComparisonJob.status.in_(
                    ACTIVE_REVISION_COMPARISON_JOB_STATUSES
                ),
            )
        )

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        document_id: UUID | None,
        statuses: Sequence[RevisionComparisonJobStatus] | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[RevisionComparisonJob], int]:
        predicates: list[ColumnElement[bool]] = []
        if department_ids is not None:
            if not department_ids:
                return [], 0
            predicates.append(Document.department_id.in_(department_ids))
        if document_id is not None:
            predicates.append(
                RevisionComparisonJob.document_id == document_id
            )
        if statuses:
            predicates.append(RevisionComparisonJob.status.in_(statuses))
        if requested_from is not None:
            predicates.append(
                RevisionComparisonJob.requested_at >= requested_from
            )
        if requested_to is not None:
            predicates.append(
                RevisionComparisonJob.requested_at <= requested_to
            )
        base = (
            select(RevisionComparisonJob)
            .join(Document, Document.id == RevisionComparisonJob.document_id)
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                RevisionComparisonJob.requested_at.desc(),
                RevisionComparisonJob.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total
