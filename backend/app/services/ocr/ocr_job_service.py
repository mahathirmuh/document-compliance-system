"""Authenticated OCR queue, history, cancellation, and re-OCR orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    AuditAction,
    Permission,
    has_permission,
)
from app.core.config import Settings
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extracted_container import ExtractedContainer
from app.models.extraction_run import ExtractorType
from app.models.ocr_job import (
    ACTIVE_OCR_JOB_STATUSES,
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
)
from app.models.ocr_run import OCRRun
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.ocr_job_repository import OCRJobRepository
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.common import PaginationData
from app.schemas.extraction_job import (
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)
from app.schemas.ocr import (
    OCRCancelResponse,
    OCRJobError,
    OCRJobListItem,
    OCRJobResponse,
    OCRQueuedResponse,
    OCRReprocessRequest,
    OCRStartRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
)
from app.services.ocr.base_ocr_provider import OCRError
from app.services.ocr.ocr_page_service import OCRPageService
from app.services.ocr.ocr_preprocessing_service import (
    OCRPreprocessingService,
)
from app.services.ocr.ocr_provider_factory import get_ocr_provider
from app.services.ocr.ocr_render_service import OCRRenderService
from app.utils.datetime import utc_now


def ocr_job_not_found() -> Exception:
    return document_error(
        "The OCR job does not exist or is outside your access scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="OCR job was not found.",
    )


def ocr_run_not_found() -> Exception:
    return document_error(
        "The OCR run does not exist or is outside your access scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="OCR result was not found.",
    )


class OCRJobService(DocumentServiceBase):
    """Validate, durably queue, inspect, list, and cancel local OCR."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.jobs = OCRJobRepository(session)
        self.runs = OCRRunRepository(session)
        self.extraction_runs = ExtractionRunRepository(session)
        self.files = DocumentFileRepository(session)

    async def start(self, payload: OCRStartRequest) -> OCRQueuedResponse:
        return await self._queue(
            payload,
            reason=None,
            re_ocr_source=None,
        )

    async def reocr(
        self,
        run_id: UUID,
        payload: OCRReprocessRequest,
    ) -> OCRQueuedResponse:
        self._ensure_permission(Permission.DOCUMENTS_REOCR)
        old_run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(old_run)
        assert old_run is not None
        old_pages = list(
            old_run.ocr_job.requested_page_numbers_json
            if old_run.ocr_job is not None
            else []
        )
        return await self._queue(
            OCRStartRequest(
                document_file_id=old_run.document_file_id,
                extraction_run_id=old_run.source_extraction_run_id,
                language_profile=(payload.language_profile or old_run.language_profile),
                page_numbers=payload.page_numbers or old_pages or None,
                preprocessing_profile=(
                    payload.preprocessing_profile or old_run.preprocessing_profile
                ),
                force=True,
            ),
            reason=payload.reason,
            re_ocr_source=old_run,
        )

    async def _queue(
        self,
        payload: OCRStartRequest,
        *,
        reason: str | None,
        re_ocr_source: OCRRun | None,
    ) -> OCRQueuedResponse:
        permission = (
            Permission.DOCUMENTS_REOCR if payload.force else Permission.DOCUMENTS_OCR
        )
        self._ensure_permission(permission)
        document_file = await self._ocr_eligible_file(
            payload.document_file_id,
            for_update=True,
        )
        extraction_run = await self.extraction_runs.get_by_id(payload.extraction_run_id)
        if (
            extraction_run is None
            or extraction_run.document_file_id != document_file.id
            or extraction_run.document_id != document_file.document_id
            or extraction_run.document_revision_id != document_file.document_revision_id
            or extraction_run.extractor_type is not ExtractorType.PDF
        ):
            raise document_error(
                "The selected PDF extraction result is not valid for this file.",
                field="extractionRunId",
                title="OCR source is not available.",
            )
        can_reocr = has_permission(
            self.user.role,
            Permission.DOCUMENTS_REOCR,
            is_superuser=self.user.is_superuser,
        )
        if (
            not can_reocr
            and document_file.latest_extraction_run_id != extraction_run.id
        ):
            raise document_error(
                "Only the latest extraction result can start initial OCR.",
                field="extractionRunId",
                title="OCR source is not available.",
            )

        active_job = await self.jobs.find_active_by_file(
            document_file.id,
            for_update=True,
        )
        if active_job is not None:
            raise document_conflict(
                "An active OCR job already exists for this file.",
                field="documentFileId",
                title="Active OCR job already exists.",
            )
        await self.jobs.acquire_user_concurrency_lock(self.user.id)
        maximum_user_jobs = int(
            getattr(self.settings, "ocr_max_concurrent_jobs_per_user", 3)
        )
        if await self.jobs.count_active_by_user(self.user.id) >= maximum_user_jobs:
            raise document_conflict(
                "You have reached the active OCR job limit.",
                title="OCR concurrency limit reached.",
            )

        containers = list(
            await self.session.scalars(
                select(ExtractedContainer)
                .where(ExtractedContainer.extraction_run_id == extraction_run.id)
                .order_by(ExtractedContainer.container_index)
            )
        )
        page_service = self._page_service()
        try:
            selection = page_service.select_pages(
                extraction_run,
                containers,
                requested_page_numbers=payload.page_numbers,
                force=payload.force,
            )
        except OCRError as exc:
            raise document_error(
                exc.safe_message,
                field="pageNumbers",
                title="OCR pages could not be selected.",
            ) from exc
        if not selection.selected_page_numbers:
            raise document_error(
                "No PDF pages require OCR. Use force only for an approved re-OCR.",
                field="pageNumbers",
                title="No pages require OCR.",
            )

        provider = get_ocr_provider(self.settings)
        provider_info = provider.get_provider_info()
        job = OCRJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            job_type=(
                OCRJobType.RE_OCR
                if re_ocr_source is not None
                else (
                    OCRJobType.MANUAL_PAGE_OCR
                    if payload.force and payload.page_numbers is not None
                    else OCRJobType.INITIAL_OCR
                )
            ),
            status=OCRJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            language_profile=payload.language_profile,
            preprocessing_profile=payload.preprocessing_profile,
            requested_page_numbers_json=(selection.selected_page_numbers),
            processed_page_numbers_json=[],
            failed_page_numbers_json=[],
            requested_by=self.user.id,
            maximum_attempts=(int(getattr(self.settings, "ocr_max_retries", 1)) + 1),
            provider=str(provider_info.get("name") or "paddleocr"),
            provider_version=(
                str(provider_info["version"]) if provider_info.get("version") else None
            ),
            result_summary_json={
                "pageSelection": selection.model_dump(
                    mode="json",
                    by_alias=True,
                ),
                **({"reOcrReason": reason} if reason is not None else {}),
                **(
                    {"sourceOcrRunId": str(re_ocr_source.id)}
                    if re_ocr_source is not None
                    else {}
                ),
            },
        )
        try:
            await self.jobs.create(job)
            await self.audit(
                action=(
                    AuditAction.REOCR_DOCUMENT
                    if re_ocr_source is not None
                    else AuditAction.QUEUE_OCR
                ),
                entity_type="OCRJob",
                entity_id=job.id,
                description=(
                    "Document re-OCR queued."
                    if re_ocr_source is not None
                    else "Document OCR queued."
                ),
                new_values={
                    "documentFileId": str(document_file.id),
                    "extractionRunId": str(extraction_run.id),
                    "languageProfile": payload.language_profile.value,
                    "pageNumbers": selection.selected_page_numbers,
                    **({"reason": reason} if reason else {}),
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "An active OCR job already exists for this file.",
                field="documentFileId",
                title="Active OCR job already exists.",
            ) from exc

        await self._dispatch(job)
        return OCRQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            page_numbers=job.requested_page_numbers_json,
            document_file_id=job.document_file_id,
        )

    async def get(self, job_id: UUID) -> OCRJobResponse:
        self._ensure_any_view_permission()
        job = await self.jobs.get_by_id(job_id)
        self._ensure_job_access(job)
        assert job is not None
        return ocr_job_detail(job)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        document_id: UUID | None,
        revision_id: UUID | None,
        document_file_id: UUID | None,
        statuses: Sequence[OCRJobStatus] | None,
        language_profile: OCRLanguageProfile | None,
        requested_by: UUID | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> PaginationData[OCRJobListItem]:
        self._ensure_any_view_permission()
        items, total = await self.jobs.list(
            search=search,
            department_id=department_id,
            document_id=document_id,
            revision_id=revision_id,
            document_file_id=document_file_id,
            statuses=statuses,
            language_profile=language_profile,
            requested_by=requested_by,
            requested_from=requested_from,
            requested_to=requested_to,
            scope_all_departments=self.policy.view_all_departments,
            scope_department_id=self.policy.scope_department_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginationData(
            items=[ocr_job_item(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def cancel(self, job_id: UUID) -> OCRCancelResponse:
        self._ensure_permission(Permission.DOCUMENTS_CANCEL_OCR)
        job = await self.jobs.get_by_id(job_id, for_update=True)
        self._ensure_job_access(job)
        assert job is not None
        if job.status not in ACTIVE_OCR_JOB_STATUSES:
            raise document_conflict(
                "Only an active OCR job can be cancelled.",
                title="OCR job cannot be cancelled.",
            )
        if job.status is not OCRJobStatus.CANCEL_REQUESTED:
            await self.jobs.mark_cancel_requested(job)
            await self.audit(
                action=AuditAction.CANCEL_OCR,
                entity_type="OCRJob",
                entity_id=job.id,
                description="OCR cancellation requested.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "status": OCRJobStatus.CANCEL_REQUESTED.value,
                },
            )
            await self.session.commit()
        return OCRCancelResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            current_stage=job.current_stage,
            cancelled_at=job.cancelled_at,
        )

    async def _ocr_eligible_file(
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
            raise document_error(
                "The document file does not exist or is outside your access scope.",
                status_code=HTTPStatus.NOT_FOUND,
                title="Document file was not found.",
            )
        self.policy.ensure_document_access(document_file.document)
        if document_file.document.is_archived:
            raise document_error(
                "Archived documents cannot start OCR.",
                field="documentFileId",
                title="Document file is not available for OCR.",
            )
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
        ):
            raise document_error(
                "Only the current available document file can be processed.",
                field="documentFileId",
                title="Document file is not available for OCR.",
            )
        if document_file.file_extension.lower() != "pdf":
            raise document_error(
                "OCR is supported only for PDF files.",
                field="documentFileId",
                title="Unsupported OCR file type.",
            )
        return document_file

    def _page_service(self) -> OCRPageService:
        return OCRPageService(
            get_ocr_provider(self.settings),
            OCRRenderService(
                dpi=int(getattr(self.settings, "ocr_render_dpi", 300)),
                image_format=str(getattr(self.settings, "ocr_render_format", "png")),
                maximum_width=int(getattr(self.settings, "ocr_max_render_width", 6000)),
                maximum_height=int(
                    getattr(self.settings, "ocr_max_render_height", 6000)
                ),
            ),
            OCRPreprocessingService(),
            selectable_text_minimum=int(
                getattr(
                    self.settings,
                    "ocr_selectable_text_min_characters",
                    50,
                )
            ),
            skip_pages_with_selectable_text=bool(
                getattr(
                    self.settings,
                    "ocr_skip_pages_with_selectable_text",
                    True,
                )
            ),
            maximum_pages=int(getattr(self.settings, "ocr_max_pages_per_job", 500)),
            maximum_page_retries=int(getattr(self.settings, "ocr_max_retries", 1)),
            low_confidence_threshold=float(
                getattr(
                    self.settings,
                    "ocr_low_confidence_threshold",
                    0.60,
                )
            ),
        )

    async def _dispatch(self, job: OCRJob) -> None:
        try:
            from app.workers.ocr_tasks import process_ocr_job

            result = process_ocr_job.apply_async(
                args=[str(job.id)],
                queue=str(getattr(self.settings, "ocr_queue_name", "ocr")),
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
                    error_code="OCR_PROVIDER_UNAVAILABLE",
                    error_message="The OCR worker could not accept this job.",
                )
                await self.audit(
                    action=AuditAction.FAIL_OCR,
                    entity_type="OCRJob",
                    entity_id=fresh_job.id,
                    description="OCR dispatch failed.",
                    new_values={
                        "documentFileId": str(fresh_job.document_file_id),
                        "errorCode": "OCR_PROVIDER_UNAVAILABLE",
                    },
                )
                await self.session.commit()
            raise document_error(
                "The OCR worker is temporarily unavailable.",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="OCR could not be queued.",
            ) from exc

    def _ensure_job_access(self, job: OCRJob | None) -> None:
        if job is None:
            raise ocr_job_not_found()
        try:
            self.policy.ensure_document_access(job.document)
        except Exception as exc:
            raise ocr_job_not_found() from exc

    def _ensure_run_access(self, run: OCRRun | None) -> None:
        if run is None:
            raise ocr_run_not_found()
        try:
            self.policy.ensure_document_access(run.document)
        except Exception as exc:
            raise ocr_run_not_found() from exc

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
            Permission.DOCUMENTS_VIEW_OCR_RESULTS,
            Permission.DOCUMENTS_VIEW_OCR_HISTORY,
            Permission.DOCUMENTS_OCR,
            Permission.DOCUMENTS_REOCR,
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


def ocr_job_item(job: OCRJob) -> OCRJobListItem:
    """Serialize a fully loaded job without worker/error internals."""
    return OCRJobListItem(
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
        extraction_run_id=job.extraction_run_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        language_profile=job.language_profile,
        preprocessing_profile=job.preprocessing_profile,
        provider=job.provider,
        provider_version=job.provider_version,
        page_numbers=list(job.requested_page_numbers_json),
        processed_page_numbers=list(job.processed_page_numbers_json),
        failed_page_numbers=list(job.failed_page_numbers_json),
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
        run_id=job.ocr_run.id if job.ocr_run is not None else None,
        result_summary=job.result_summary_json,
    )


def ocr_job_detail(job: OCRJob) -> OCRJobResponse:
    item = ocr_job_item(job)
    return OCRJobResponse(
        **item.model_dump(),
        attempt_number=job.attempt_number,
        maximum_attempts=job.maximum_attempts,
        failed_at=job.failed_at,
        error=(
            OCRJobError(
                code=job.error_code,
                message=job.error_message or "OCR processing failed.",
            )
            if job.error_code is not None
            else None
        ),
    )
