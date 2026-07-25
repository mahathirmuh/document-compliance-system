"""Database-only operations for language detection jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.language_detection_job import (
    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES,
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
)


class LanguageDetectionJobRepository:
    """Persist job state without business rules or broker dispatch."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(LanguageDetectionJob.document),
            joinedload(LanguageDetectionJob.revision),
            joinedload(LanguageDetectionJob.document_file),
            joinedload(LanguageDetectionJob.requester),
            joinedload(LanguageDetectionJob.detection_run),
        )

    async def create(
        self,
        job: LanguageDetectionJob,
    ) -> LanguageDetectionJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> LanguageDetectionJob | None:
        statement = (
            select(LanguageDetectionJob)
            .where(LanguageDetectionJob.id == job_id)
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(of=LanguageDetectionJob)
        return await self.session.scalar(statement)

    async def find_active_by_file(
        self,
        document_file_id: UUID,
        *,
        for_update: bool = False,
    ) -> LanguageDetectionJob | None:
        statement = (
            select(LanguageDetectionJob)
            .where(
                LanguageDetectionJob.document_file_id == document_file_id,
                LanguageDetectionJob.status.in_(
                    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES
                ),
            )
            .options(*self._options())
            .order_by(
                LanguageDetectionJob.requested_at.desc(),
                LanguageDetectionJob.id.desc(),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=LanguageDetectionJob)
        return await self.session.scalar(statement)

    async def list(
        self,
        *,
        search: str | None = None,
        department_id: UUID | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        document_file_id: UUID | None = None,
        statuses: Sequence[LanguageDetectionJobStatus] | None = None,
        requested_by: UUID | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        scope_all_departments: bool = False,
        scope_department_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "requestedAt",
        sort_order: str = "desc",
    ) -> tuple[list[LanguageDetectionJob], int]:
        predicates: list[object] = []
        if department_id is not None:
            predicates.append(Document.department_id == department_id)
        if document_id is not None:
            predicates.append(
                LanguageDetectionJob.document_id == document_id
            )
        if revision_id is not None:
            predicates.append(
                LanguageDetectionJob.document_revision_id == revision_id
            )
        if document_file_id is not None:
            predicates.append(
                LanguageDetectionJob.document_file_id == document_file_id
            )
        if statuses:
            predicates.append(LanguageDetectionJob.status.in_(statuses))
        if requested_by is not None:
            predicates.append(
                LanguageDetectionJob.requested_by == requested_by
            )
        if requested_from is not None:
            predicates.append(
                LanguageDetectionJob.requested_at >= requested_from
            )
        if requested_to is not None:
            predicates.append(
                LanguageDetectionJob.requested_at < requested_to
            )
        if not scope_all_departments:
            predicates.append(
                Document.department_id == scope_department_id
                if scope_department_id is not None
                else false()
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    DocumentRevision.full_document_code.ilike(pattern),
                    DocumentFile.original_filename.ilike(pattern),
                )
            )

        base = (
            select(LanguageDetectionJob)
            .join(
                Document,
                Document.id == LanguageDetectionJob.document_id,
            )
            .join(
                DocumentRevision,
                DocumentRevision.id
                == LanguageDetectionJob.document_revision_id,
            )
            .join(
                DocumentFile,
                DocumentFile.id
                == LanguageDetectionJob.document_file_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        sort_columns = {
            "requestedAt": LanguageDetectionJob.requested_at,
            "completedAt": LanguageDetectionJob.completed_at,
            "status": LanguageDetectionJob.status,
            "progress": LanguageDetectionJob.progress,
        }
        sort_column = sort_columns.get(
            sort_by,
            LanguageDetectionJob.requested_at,
        )
        ascending = sort_order.lower() == "asc"
        ordering = (
            sort_column.asc().nullslast()
            if ascending
            else sort_column.desc().nullslast()
        )
        tie_breaker = (
            LanguageDetectionJob.id.asc()
            if ascending
            else LanguageDetectionJob.id.desc()
        )
        items = list(
            (
                await self.session.scalars(
                    base.options(*self._options())
                    .order_by(ordering, tie_breaker)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .unique()
            .all()
        )
        return items, total

    async def update_status(
        self,
        job: LanguageDetectionJob,
        *,
        status: LanguageDetectionJobStatus,
        progress: int | None = None,
        current_stage: str | None = None,
        started_at: datetime | None = None,
    ) -> LanguageDetectionJob:
        job.status = status
        if progress is not None:
            job.progress = progress
        if current_stage is not None:
            job.current_stage = current_stage
        if started_at is not None:
            job.started_at = started_at
        await self.session.flush()
        return job

    async def update_progress(
        self,
        job: LanguageDetectionJob,
        *,
        progress: int,
        current_stage: str,
    ) -> LanguageDetectionJob:
        job.progress = progress
        job.current_stage = current_stage
        await self.session.flush()
        return job

    async def mark_completed(
        self,
        job: LanguageDetectionJob,
        *,
        status: LanguageDetectionJobStatus,
        completed_at: datetime,
        result_summary: dict[str, object],
    ) -> LanguageDetectionJob:
        if status not in {
            LanguageDetectionJobStatus.COMPLETED,
            LanguageDetectionJobStatus.PARTIALLY_COMPLETED,
        }:
            raise ValueError("Completed job requires a result status.")
        job.status = status
        job.progress = 100
        job.current_stage = "Completed"
        job.completed_at = completed_at
        job.result_summary_json = {
            **(job.result_summary_json or {}),
            **result_summary,
        }
        job.error_code = None
        job.error_message = None
        job.error_details_json = None
        await self.session.flush()
        return job

    async def mark_failed(
        self,
        job: LanguageDetectionJob,
        *,
        failed_at: datetime,
        error_code: str,
        error_message: str,
        error_details: dict[str, object] | None = None,
    ) -> LanguageDetectionJob:
        job.status = LanguageDetectionJobStatus.FAILED
        job.current_stage = "Failed"
        job.failed_at = failed_at
        job.error_code = error_code
        job.error_message = error_message
        job.error_details_json = error_details
        await self.session.flush()
        return job

    async def mark_cancel_requested(
        self,
        job: LanguageDetectionJob,
    ) -> LanguageDetectionJob:
        job.status = LanguageDetectionJobStatus.CANCEL_REQUESTED
        job.current_stage = "Cancellation requested"
        await self.session.flush()
        return job

    async def mark_cancelled(
        self,
        job: LanguageDetectionJob,
        *,
        cancelled_at: datetime,
    ) -> LanguageDetectionJob:
        job.status = LanguageDetectionJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = cancelled_at
        await self.session.flush()
        return job
