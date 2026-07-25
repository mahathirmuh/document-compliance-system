"""User-facing extraction job orchestration and response serialization."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extraction_job import (
    ACTIVE_EXTRACTION_JOB_STATUSES,
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import ExtractorType
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_job_repository import ExtractionJobRepository
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.schemas.common import PaginationData
from app.schemas.extraction_job import (
    ExtractionCancelResponse,
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionJobDetailResponse,
    ExtractionJobError,
    ExtractionJobListItem,
    ExtractionQueuedResponse,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
)
from app.utils.datetime import utc_now

TERMINAL_EXTRACTION_JOB_STATUSES = frozenset(
    {
        ExtractionJobStatus.COMPLETED,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
        ExtractionJobStatus.OCR_REQUIRED,
        ExtractionJobStatus.FAILED,
        ExtractionJobStatus.CANCELLED,
    }
)


def extraction_not_found() -> Exception:
    return document_error(
        "The extraction job does not exist or is outside your access scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Extraction job was not found.",
    )


def extraction_file_not_found() -> Exception:
    return document_error(
        "The document file does not exist or is outside your access scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Document file was not found.",
    )


class ExtractionJobService(DocumentServiceBase):
    """Validate, queue, list, inspect, and cancel extraction jobs."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.jobs = ExtractionJobRepository(session)
        self.runs = ExtractionRunRepository(session)
        self.files = DocumentFileRepository(session)

    async def start(
        self,
        document_file_id: UUID,
        *,
        force: bool,
    ) -> ExtractionQueuedResponse:
        """Create a durable job before dispatching it to Celery."""
        permission = (
            Permission.DOCUMENTS_REEXTRACT
            if force
            else Permission.DOCUMENTS_EXTRACT
        )
        self._ensure_permission(permission)
        document_file = await self._extractable_file(
            document_file_id,
            for_update=True,
        )

        active_job = await self.jobs.find_active_by_file(
            document_file.id,
            for_update=True,
        )
        if active_job is not None:
            raise document_conflict(
                "An active extraction already exists for this file.",
                field="documentFileId",
                title="Active extraction already exists.",
            )

        existing_run = await self.runs.find_by_source_hash(
            document_file.id,
            document_file.sha256_hash,
        )
        if existing_run is not None and not force:
            existing_job = existing_run.extraction_job
            return ExtractionQueuedResponse(
                job_id=existing_job.id,
                status=existing_job.status,
                progress=existing_job.progress,
                document_file_id=document_file.id,
                reused_existing_result=True,
                run_id=existing_run.id,
            )

        job = ExtractionJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            job_type=(
                ExtractionJobType.RE_EXTRACTION
                if force
                else ExtractionJobType.INITIAL_EXTRACTION
            ),
            status=ExtractionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            requested_by=self.user.id,
            maximum_attempts=self.settings.extraction_max_retries + 1,
        )
        try:
            await self.jobs.create(job)
            await self.audit(
                action=(
                    AuditAction.REEXTRACT_DOCUMENT
                    if force
                    else AuditAction.QUEUE_DOCUMENT_EXTRACTION
                ),
                entity_type="ExtractionJob",
                entity_id=job.id,
                description=(
                    "Document re-extraction queued."
                    if force
                    else "Document extraction queued."
                ),
                new_values={
                    "documentFileId": str(document_file.id),
                    "jobType": job.job_type.value,
                    "sourceSha256Hash": document_file.sha256_hash,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "An active extraction already exists for this file.",
                field="documentFileId",
                title="Active extraction already exists.",
            ) from exc

        await self._dispatch(job)
        return ExtractionQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            document_file_id=document_file.id,
        )

    async def reextract(
        self,
        document_file_id: UUID,
        *,
        reason: str,
    ) -> ExtractionQueuedResponse:
        self._ensure_permission(Permission.DOCUMENTS_REEXTRACT)
        document_file = await self._extractable_file(
            document_file_id,
            for_update=True,
        )
        active_job = await self.jobs.find_active_by_file(
            document_file.id,
            for_update=True,
        )
        if active_job is not None:
            raise document_conflict(
                "An active extraction already exists for this file.",
                field="documentFileId",
                title="Active extraction already exists.",
            )

        job = ExtractionJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.RE_EXTRACTION,
            status=ExtractionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued for re-extraction",
            requested_by=self.user.id,
            maximum_attempts=self.settings.extraction_max_retries + 1,
            result_summary_json={"reExtractionReason": reason},
        )
        try:
            await self.jobs.create(job)
            await self.audit(
                action=AuditAction.REEXTRACT_DOCUMENT,
                entity_type="ExtractionJob",
                entity_id=job.id,
                description="Document re-extraction queued.",
                new_values={
                    "documentFileId": str(document_file.id),
                    "reason": reason,
                    "sourceSha256Hash": document_file.sha256_hash,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "An active extraction already exists for this file.",
                field="documentFileId",
                title="Active extraction already exists.",
            ) from exc

        await self._dispatch(job)
        return ExtractionQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            document_file_id=document_file.id,
        )

    async def get(self, job_id: UUID) -> ExtractionJobDetailResponse:
        self._ensure_any_view_permission()
        job = await self.jobs.get_by_id(job_id)
        self._ensure_job_access(job)
        assert job is not None
        return extraction_job_detail(job)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        document_id: UUID | None,
        revision_id: UUID | None,
        document_file_id: UUID | None,
        extractor_type: ExtractorType | None,
        statuses: Sequence[ExtractionJobStatus] | None,
        requested_by: UUID | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> PaginationData[ExtractionJobListItem]:
        self._ensure_any_view_permission()
        items, total = await self.jobs.list(
            search=search,
            department_id=department_id,
            document_id=document_id,
            revision_id=revision_id,
            document_file_id=document_file_id,
            extractor_type=extractor_type,
            statuses=statuses,
            requested_by=requested_by,
            requested_from=requested_from,
            requested_to=requested_to,
            scope_all_departments=self.policy.view_all_departments,
            scope_department_id=self.policy.scope_department_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginationData(
            items=[extraction_job_item(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def cancel(self, job_id: UUID) -> ExtractionCancelResponse:
        self._ensure_permission(Permission.DOCUMENTS_CANCEL_EXTRACTION)
        job = await self.jobs.get_by_id(job_id, for_update=True)
        self._ensure_job_access(job)
        assert job is not None
        if job.status not in ACTIVE_EXTRACTION_JOB_STATUSES:
            raise document_conflict(
                "Only an active extraction job can be cancelled.",
                title="Extraction job cannot be cancelled.",
            )

        if job.status is not ExtractionJobStatus.CANCEL_REQUESTED:
            await self.jobs.mark_cancel_requested(job)
            await self.audit(
                action=AuditAction.CANCEL_DOCUMENT_EXTRACTION,
                entity_type="ExtractionJob",
                entity_id=job.id,
                description="Document extraction cancellation requested.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "status": ExtractionJobStatus.CANCEL_REQUESTED.value,
                },
            )
            await self.session.commit()

        return ExtractionCancelResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            current_stage=job.current_stage,
            cancelled_at=job.cancelled_at,
        )

    async def _extractable_file(
        self,
        file_id: UUID,
        *,
        for_update: bool,
    ) -> DocumentFile:
        document_file = await self.files.get_by_id(
            file_id,
            for_update=for_update,
        )
        if document_file is None:
            raise extraction_file_not_found()
        self.policy.ensure_document_access(document_file.document)
        if document_file.document.is_archived:
            raise document_error(
                "Archived documents cannot start extraction.",
                field="documentFileId",
                title="Document file is not available for extraction.",
            )
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
        ):
            raise document_error(
                "Only the current available document file can be extracted.",
                field="documentFileId",
                title="Document file is not available for extraction.",
            )
        if document_file.file_extension not in {"pdf", "docx", "xlsx"}:
            raise document_error(
                "This file format is not supported for extraction.",
                field="documentFileId",
                title="Unsupported extraction format.",
            )
        return document_file

    async def _dispatch(self, job: ExtractionJob) -> None:
        try:
            from app.workers.extraction_tasks import process_extraction_job

            result = process_extraction_job.apply_async(
                args=[str(job.id)],
                queue=self.settings.extraction_queue_name,
            )
            job.worker_reference = str(result.id)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            fresh_job = await self.jobs.get_by_id(job.id, for_update=True)
            if fresh_job is not None:
                await self.jobs.mark_failed(
                    fresh_job,
                    failed_at=utc_now(),
                    error_code="EXTRACTION_WORKER_FAILED",
                    error_message=(
                        "The extraction worker could not accept this job."
                    ),
                )
                await self.audit(
                    action=AuditAction.FAIL_DOCUMENT_EXTRACTION,
                    entity_type="ExtractionJob",
                    entity_id=fresh_job.id,
                    description="Document extraction dispatch failed.",
                    new_values={
                        "documentFileId": str(
                            fresh_job.document_file_id
                        ),
                        "errorCode": "EXTRACTION_WORKER_FAILED",
                    },
                )
                await self.session.commit()
            raise document_error(
                "The extraction worker is temporarily unavailable.",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="Document extraction could not be queued.",
            ) from exc

    def _ensure_job_access(self, job: ExtractionJob | None) -> None:
        if job is None:
            raise extraction_not_found()
        try:
            self.policy.ensure_document_access(job.document)
        except Exception as exc:
            raise extraction_not_found() from exc

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError()

    def _ensure_any_view_permission(self) -> None:
        permissions = (
            Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
            Permission.DOCUMENTS_EXTRACT,
        )
        if not any(
            has_permission(
                self.user.role,
                permission,
                is_superuser=self.user.is_superuser,
            )
            for permission in permissions
        ):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError()


def extraction_job_item(job: ExtractionJob) -> ExtractionJobListItem:
    """Serialize a fully loaded job without exposing worker/error internals."""
    return ExtractionJobListItem(
        id=job.id,
        document=ExtractionDocumentReference(
            id=job.document.id,
            base_document_code=job.document.base_document_code,
            title=job.document.title,
            department_id=job.document.department_id,
        ),
        revision=ExtractionRevisionReference(
            id=job.revision.id,
            revision_code=job.revision.revision_code,
            full_document_code=job.revision.full_document_code,
        ),
        file=ExtractionFileReference(
            id=job.document_file.id,
            filename=job.document_file.original_filename,
            extension=job.document_file.file_extension,
            sha256_hash=job.document_file.sha256_hash,
        ),
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        requested_by=(
            ExtractionRequesterReference(
                id=job.requester.id,
                name=job.requester.name,
            )
            if job.requester is not None
            else None
        ),
        requested_at=job.requested_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
        run_id=(
            job.extraction_run.id
            if job.extraction_run is not None
            else None
        ),
        result_summary=job.result_summary_json,
    )


def extraction_job_detail(job: ExtractionJob) -> ExtractionJobDetailResponse:
    item = extraction_job_item(job)
    return ExtractionJobDetailResponse(
        **item.model_dump(),
        attempt_number=job.attempt_number,
        maximum_attempts=job.maximum_attempts,
        failed_at=job.failed_at,
        error=(
            ExtractionJobError(
                code=job.error_code,
                message=job.error_message
                or "Document extraction failed.",
            )
            if job.error_code is not None
            else None
        ),
    )
