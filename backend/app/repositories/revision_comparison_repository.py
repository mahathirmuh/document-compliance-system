"""Database-only operations for retained revision comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.revision_comparison import RevisionComparison
from app.models.revision_comparison_job import RevisionComparisonJob


class RevisionComparisonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, comparison: RevisionComparison
    ) -> RevisionComparison:
        self.session.add(comparison)
        await self.session.flush()
        return comparison

    async def get_by_id(
        self,
        comparison_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
    ) -> RevisionComparison | None:
        statement = (
            select(RevisionComparison)
            .join(Document, Document.id == RevisionComparison.document_id)
            .where(RevisionComparison.id == comparison_id)
        )
        if department_ids is not None:
            if not department_ids:
                return None
            statement = statement.where(
                Document.department_id.in_(department_ids)
            )
        return await self.session.scalar(statement)

    async def get_by_job_id(
        self, job_id: UUID
    ) -> RevisionComparison | None:
        return await self.session.scalar(
            select(RevisionComparison).where(
                RevisionComparison.revision_comparison_job_id == job_id
            )
        )

    async def find_equivalent(
        self,
        *,
        document_id: UUID,
        base_revision_id: UUID,
        target_revision_id: UUID,
        base_content_hash: str | None,
        target_content_hash: str | None,
    ) -> RevisionComparison | None:
        return await self.session.scalar(
            select(RevisionComparison)
            .where(
                RevisionComparison.document_id == document_id,
                RevisionComparison.base_revision_id == base_revision_id,
                RevisionComparison.target_revision_id == target_revision_id,
                RevisionComparison.base_content_hash == base_content_hash,
                RevisionComparison.target_content_hash
                == target_content_hash,
            )
            .order_by(RevisionComparison.created_at.desc())
            .limit(1)
        )

    async def list_by_document(
        self,
        document_id: UUID,
        *,
        department_ids: Sequence[UUID] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[RevisionComparison], int]:
        predicates: list[object] = [
            RevisionComparison.document_id == document_id
        ]
        if department_ids is not None:
            if not department_ids:
                return [], 0
            predicates.append(Document.department_id.in_(department_ids))
        base = (
            select(RevisionComparison)
            .join(Document, Document.id == RevisionComparison.document_id)
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
                RevisionComparison.created_at.desc(),
                RevisionComparison.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def job_for(
        self, comparison_id: UUID
    ) -> RevisionComparisonJob | None:
        return await self.session.scalar(
            select(RevisionComparisonJob)
            .join(
                RevisionComparison,
                RevisionComparison.revision_comparison_job_id
                == RevisionComparisonJob.id,
            )
            .where(RevisionComparison.id == comparison_id)
        )
