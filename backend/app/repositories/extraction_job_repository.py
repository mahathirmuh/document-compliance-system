"""Persistence operations for document extraction jobs."""

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
from app.models.extraction_job import (
    ACTIVE_EXTRACTION_JOB_STATUSES,
    ExtractionJob,
    ExtractionJobStatus,
)
from app.models.extraction_run import ExtractorType


class ExtractionJobRepository:
    """Database-only extraction-job operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(ExtractionJob.document),
            joinedload(ExtractionJob.revision),
            joinedload(ExtractionJob.document_file),
            joinedload(ExtractionJob.requester),
            joinedload(ExtractionJob.extraction_run),
        )

    async def create(self, job: ExtractionJob) -> ExtractionJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExtractionJob | None:
        statement = (
            select(ExtractionJob)
            .where(ExtractionJob.id == job_id)
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(of=ExtractionJob)
        return await self.session.scalar(statement)

    async def find_active_by_file(
        self,
        document_file_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExtractionJob | None:
        statement = (
            select(ExtractionJob)
            .where(
                ExtractionJob.document_file_id == document_file_id,
                ExtractionJob.status.in_(ACTIVE_EXTRACTION_JOB_STATUSES),
            )
            .options(*self._options())
            .order_by(
                ExtractionJob.requested_at.desc(),
                ExtractionJob.id.desc(),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ExtractionJob)
        return await self.session.scalar(statement)

    async def list(
        self,
        *,
        search: str | None = None,
        department_id: UUID | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        document_file_id: UUID | None = None,
        extractor_type: ExtractorType | None = None,
        statuses: Sequence[ExtractionJobStatus] | None = None,
        requested_by: UUID | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        scope_all_departments: bool = False,
        scope_department_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "requestedAt",
        sort_order: str = "desc",
    ) -> tuple[list[ExtractionJob], int]:
        predicates: list[object] = []
        if department_id is not None:
            predicates.append(Document.department_id == department_id)
        if document_id is not None:
            predicates.append(ExtractionJob.document_id == document_id)
        if revision_id is not None:
            predicates.append(
                ExtractionJob.document_revision_id == revision_id
            )
        if document_file_id is not None:
            predicates.append(
                ExtractionJob.document_file_id == document_file_id
            )
        if extractor_type is not None:
            predicates.append(
                DocumentFile.file_extension
                == extractor_type.value.lower()
            )
        if statuses:
            predicates.append(ExtractionJob.status.in_(statuses))
        if requested_by is not None:
            predicates.append(ExtractionJob.requested_by == requested_by)
        if requested_from is not None:
            predicates.append(ExtractionJob.requested_at >= requested_from)
        if requested_to is not None:
            predicates.append(ExtractionJob.requested_at < requested_to)
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
            select(ExtractionJob)
            .join(Document, Document.id == ExtractionJob.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id
                == ExtractionJob.document_revision_id,
            )
            .join(
                DocumentFile,
                DocumentFile.id == ExtractionJob.document_file_id,
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
            "requestedAt": ExtractionJob.requested_at,
            "requested_at": ExtractionJob.requested_at,
            "completedAt": ExtractionJob.completed_at,
            "completed_at": ExtractionJob.completed_at,
            "status": ExtractionJob.status,
            "progress": ExtractionJob.progress,
        }
        sort_column = sort_columns.get(
            sort_by,
            ExtractionJob.requested_at,
        )
        ascending = sort_order.lower() == "asc"
        ordering = (
            sort_column.asc().nullslast()
            if ascending
            else sort_column.desc().nullslast()
        )
        tie_breaker = (
            ExtractionJob.id.asc()
            if ascending
            else ExtractionJob.id.desc()
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
        job: ExtractionJob,
        *,
        status: ExtractionJobStatus,
        progress: int | None = None,
        current_stage: str | None = None,
        started_at: datetime | None = None,
    ) -> ExtractionJob:
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
        job: ExtractionJob,
        *,
        progress: int,
        current_stage: str,
    ) -> ExtractionJob:
        job.progress = progress
        job.current_stage = current_stage
        await self.session.flush()
        return job

    async def mark_completed(
        self,
        job: ExtractionJob,
        *,
        status: ExtractionJobStatus,
        completed_at: datetime,
        result_summary: dict[str, object] | None = None,
    ) -> ExtractionJob:
        if status not in {
            ExtractionJobStatus.COMPLETED,
            ExtractionJobStatus.PARTIALLY_COMPLETED,
            ExtractionJobStatus.OCR_REQUIRED,
        }:
            raise ValueError("Completed job requires a result status.")
        job.status = status
        job.progress = 100
        job.current_stage = "Completed"
        job.completed_at = completed_at
        job.result_summary_json = {
            **(job.result_summary_json or {}),
            **(result_summary or {}),
        }
        job.error_code = None
        job.error_message = None
        job.error_details_json = None
        await self.session.flush()
        return job

    async def mark_failed(
        self,
        job: ExtractionJob,
        *,
        failed_at: datetime,
        error_code: str,
        error_message: str,
        error_details: dict[str, object] | None = None,
    ) -> ExtractionJob:
        job.status = ExtractionJobStatus.FAILED
        job.current_stage = "Failed"
        job.failed_at = failed_at
        job.error_code = error_code
        job.error_message = error_message
        job.error_details_json = error_details
        await self.session.flush()
        return job

    async def mark_cancel_requested(
        self,
        job: ExtractionJob,
    ) -> ExtractionJob:
        job.status = ExtractionJobStatus.CANCEL_REQUESTED
        job.current_stage = "Cancellation requested"
        await self.session.flush()
        return job

    async def mark_cancelled(
        self,
        job: ExtractionJob,
        *,
        cancelled_at: datetime,
    ) -> ExtractionJob:
        job.status = ExtractionJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = cancelled_at
        await self.session.flush()
        return job
