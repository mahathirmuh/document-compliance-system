"""Database-only persistence and querying for OCR jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.ocr_job import (
    ACTIVE_OCR_JOB_STATUSES,
    OCRJob,
    OCRJobStatus,
    OCRLanguageProfile,
)
from app.models.user import User


class OCRJobRepository:
    """Keep OCR job queries separate from authorization/business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(OCRJob.document),
            joinedload(OCRJob.revision),
            joinedload(OCRJob.document_file),
            joinedload(OCRJob.extraction_run),
            joinedload(OCRJob.requester),
            joinedload(OCRJob.ocr_run),
        )

    async def create(self, job: OCRJob) -> OCRJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> OCRJob | None:
        statement = select(OCRJob).where(OCRJob.id == job_id).options(*self._options())
        if for_update:
            statement = statement.with_for_update(of=OCRJob)
        return await self.session.scalar(statement)

    async def find_active_by_file(
        self,
        document_file_id: UUID,
        *,
        for_update: bool = False,
    ) -> OCRJob | None:
        statement = (
            select(OCRJob)
            .where(
                OCRJob.document_file_id == document_file_id,
                OCRJob.status.in_(ACTIVE_OCR_JOB_STATUSES),
            )
            .options(*self._options())
            .order_by(OCRJob.requested_at.desc(), OCRJob.id.desc())
        )
        if for_update:
            statement = statement.with_for_update(of=OCRJob)
        return await self.session.scalar(statement)

    async def count_active_by_user(self, requested_by: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(OCRJob.id)).where(
                    OCRJob.requested_by == requested_by,
                    OCRJob.status.in_(ACTIVE_OCR_JOB_STATUSES),
                )
            )
            or 0
        )

    async def acquire_user_concurrency_lock(
        self,
        requested_by: UUID,
    ) -> None:
        """Serialize PostgreSQL queue-limit checks for one requesting user."""
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        lock_key = requested_by.int & ((1 << 63) - 1)
        await self.session.execute(
            select(func.pg_advisory_xact_lock(lock_key))
        )

    async def list(
        self,
        *,
        search: str | None = None,
        department_id: UUID | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        document_file_id: UUID | None = None,
        statuses: Sequence[OCRJobStatus] | None = None,
        language_profile: OCRLanguageProfile | None = None,
        requested_by: UUID | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        scope_all_departments: bool,
        scope_department_id: UUID | None,
        offset: int = 0,
        limit: int = 100,
        sort_by: str = "requestedAt",
        sort_order: str = "desc",
    ) -> tuple[list[OCRJob], int]:
        statement: Select[tuple[OCRJob]] = select(OCRJob).join(OCRJob.document)
        predicates: list[object] = []
        if not scope_all_departments:
            if scope_department_id is None:
                return [], 0
            predicates.append(Document.department_id == scope_department_id)
        if department_id is not None:
            predicates.append(Document.department_id == department_id)
        if document_id is not None:
            predicates.append(OCRJob.document_id == document_id)
        if revision_id is not None:
            predicates.append(OCRJob.document_revision_id == revision_id)
        if document_file_id is not None:
            predicates.append(OCRJob.document_file_id == document_file_id)
        if statuses:
            predicates.append(OCRJob.status.in_(statuses))
        if language_profile is not None:
            predicates.append(OCRJob.language_profile == language_profile)
        if requested_by is not None:
            predicates.append(OCRJob.requested_by == requested_by)
        if requested_from is not None:
            predicates.append(OCRJob.requested_at >= requested_from)
        if requested_to is not None:
            predicates.append(OCRJob.requested_at <= requested_to)
        if search:
            term = f"%{search.strip()}%"
            statement = (
                statement.join(OCRJob.document_file)
                .join(OCRJob.revision)
                .outerjoin(OCRJob.requester)
            )
            predicates.append(
                or_(
                    Document.base_document_code.ilike(term),
                    Document.title.ilike(term),
                    DocumentRevision.full_document_code.ilike(term),
                    DocumentFile.original_filename.ilike(term),
                    User.name.ilike(term),
                )
            )
        if predicates:
            statement = statement.where(*predicates)

        total = int(
            await self.session.scalar(
                select(func.count()).select_from(
                    statement.with_only_columns(OCRJob.id).subquery()
                )
            )
            or 0
        )
        sort_columns = {
            "requestedAt": OCRJob.requested_at,
            "completedAt": OCRJob.completed_at,
            "status": OCRJob.status,
            "progress": OCRJob.progress,
        }
        sort_column = sort_columns.get(sort_by, OCRJob.requested_at)
        ascending = sort_order.lower() == "asc"
        ordering = (
            sort_column.asc().nullslast()
            if ascending
            else sort_column.desc().nullslast()
        )
        tie_breaker = OCRJob.id.asc() if ascending else OCRJob.id.desc()
        rows = await self.session.scalars(
            statement.options(*self._options())
            .order_by(ordering, tie_breaker)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.unique().all()), total

    async def update_status(
        self,
        job: OCRJob,
        *,
        status: OCRJobStatus,
        progress: int,
        current_stage: str | None,
        started_at: datetime | None = None,
    ) -> OCRJob:
        job.status = status
        job.progress = progress
        job.current_stage = current_stage[:500] if current_stage is not None else None
        if started_at is not None:
            job.started_at = started_at
        await self.session.flush()
        return job

    async def mark_cancel_requested(self, job: OCRJob) -> OCRJob:
        job.status = OCRJobStatus.CANCEL_REQUESTED
        job.current_stage = "Cancellation requested"
        await self.session.flush()
        return job

    async def mark_cancelled(
        self,
        job: OCRJob,
        *,
        cancelled_at: datetime,
    ) -> OCRJob:
        job.status = OCRJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = cancelled_at
        await self.session.flush()
        return job

    async def mark_failed(
        self,
        job: OCRJob,
        *,
        failed_at: datetime,
        error_code: str,
        error_message: str,
        error_details: dict[str, object] | None = None,
    ) -> OCRJob:
        job.status = OCRJobStatus.FAILED
        job.current_stage = "Failed"
        job.failed_at = failed_at
        job.error_code = error_code
        job.error_message = error_message
        job.error_details_json = error_details
        await self.session.flush()
        return job

    async def mark_completed(
        self,
        job: OCRJob,
        *,
        status: OCRJobStatus,
        completed_at: datetime,
        summary: dict[str, object],
    ) -> OCRJob:
        if status not in {
            OCRJobStatus.COMPLETED,
            OCRJobStatus.PARTIALLY_COMPLETED,
        }:
            raise ValueError("OCR completion requires a completed status.")
        job.status = status
        job.progress = 100
        job.current_stage = (
            "Completed" if status is OCRJobStatus.COMPLETED else "Partially completed"
        )
        job.completed_at = completed_at
        job.result_summary_json = summary
        await self.session.flush()
        return job
