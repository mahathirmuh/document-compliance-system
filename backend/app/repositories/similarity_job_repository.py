"""Database-only operations for similarity jobs."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.similarity_enums import (
    ACTIVE_SIMILARITY_JOB_STATUSES,
    SimilarityJobStatus,
)
from app.models.similarity_job import SimilarityJob


class SimilarityJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(SimilarityJob).options(
            joinedload(SimilarityJob.document),
            joinedload(SimilarityJob.revision),
            joinedload(SimilarityJob.document_file),
            joinedload(SimilarityJob.compliance_run),
            joinedload(SimilarityJob.language_detection_run),
            joinedload(SimilarityJob.requester),
            joinedload(SimilarityJob.similarity_run),
        )

    async def add(self, job: SimilarityJob) -> SimilarityJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> SimilarityJob | None:
        statement = self.base_statement().where(SimilarityJob.id == job_id)
        if department_ids is not None:
            statement = statement.join(
                Document, Document.id == SimilarityJob.document_id
            ).where(Document.department_id.in_(list(department_ids)))
        if for_update:
            statement = statement.with_for_update(
                of=SimilarityJob
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_active(
        self,
        document_file_id: UUID,
        *,
        source_content_hash: str | None = None,
        for_update: bool = False,
    ) -> SimilarityJob | None:
        statement = self.base_statement().where(
            SimilarityJob.document_file_id == document_file_id,
            SimilarityJob.status.in_(ACTIVE_SIMILARITY_JOB_STATUSES),
        )
        if source_content_hash is not None:
            statement = statement.where(
                SimilarityJob.source_content_hash
                == source_content_hash.strip().lower()
            )
        if for_update:
            statement = statement.with_for_update(
                of=SimilarityJob
            ).execution_options(populate_existing=True)
        return (
            await self.session.execute(
                statement.order_by(
                    desc(SimilarityJob.requested_at),
                    desc(SimilarityJob.id),
                ).limit(1)
            )
        ).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        department_id: UUID | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        document_file_id: UUID | None = None,
        compliance_run_id: UUID | None = None,
        requested_by: UUID | None = None,
        statuses: Sequence[SimilarityJobStatus] | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "requestedAt",
        sort_order: str = "desc",
    ) -> tuple[list[SimilarityJob], int]:
        statement = self.base_statement()
        if department_ids is not None or department_id is not None or search:
            statement = statement.join(
                Document, Document.id == SimilarityJob.document_id
            )
        if department_ids is not None:
            statement = statement.where(
                Document.department_id.in_(list(department_ids))
            )
        if department_id is not None:
            statement = statement.where(
                Document.department_id == department_id
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    SimilarityJob.current_stage.ilike(pattern),
                    SimilarityJob.model_name.ilike(pattern),
                )
            )
        if document_id is not None:
            statement = statement.where(
                SimilarityJob.document_id == document_id
            )
        if revision_id is not None:
            statement = statement.where(
                SimilarityJob.document_revision_id == revision_id
            )
        if document_file_id is not None:
            statement = statement.where(
                SimilarityJob.document_file_id == document_file_id
            )
        if compliance_run_id is not None:
            statement = statement.where(
                SimilarityJob.compliance_run_id == compliance_run_id
            )
        if requested_by is not None:
            statement = statement.where(
                SimilarityJob.requested_by == requested_by
            )
        if statuses:
            statement = statement.where(
                SimilarityJob.status.in_(list(statuses))
            )
        if requested_from is not None:
            statement = statement.where(
                SimilarityJob.requested_at >= requested_from
            )
        if requested_to is not None:
            statement = statement.where(
                SimilarityJob.requested_at <= requested_to
            )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        sort_columns = {
            "requestedAt": SimilarityJob.requested_at,
            "completedAt": SimilarityJob.completed_at,
            "status": SimilarityJob.status,
            "progress": SimilarityJob.progress,
        }
        column = sort_columns.get(sort_by, SimilarityJob.requested_at)
        ordering = asc(column) if sort_order == "asc" else desc(column)
        rows = await self.session.scalars(
            statement.order_by(ordering, SimilarityJob.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.unique().all()), total
