"""User-facing language job lifecycle and scoped result reads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extracted_block import ExtractedBlock
from app.models.extraction_run import ExtractionRunStatus
from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.models.language_container_summary import LanguageContainerSummary
from app.models.language_detection_job import (
    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES,
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.models.language_detection_run import LanguageDetectionRun
from app.models.ocr_block import OCRBlock
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.language_block_result_repository import (
    LanguageBlockReadRow,
    LanguageBlockResultRepository,
)
from app.repositories.language_container_summary_repository import (
    LanguageContainerSummaryRepository,
)
from app.repositories.language_detection_job_repository import (
    LanguageDetectionJobRepository,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.common import PaginationData
from app.schemas.language_detection import (
    LanguageBlockResultListResponse,
    LanguageBlockResultResponse,
    LanguageContainerSummaryListResponse,
    LanguageContainerSummaryResponse,
    LanguageCoverageResponse,
    LanguageDetectionCancelResponse,
    LanguageDetectionHistoryItem,
    LanguageDetectionJobError,
    LanguageDetectionJobListItem,
    LanguageDetectionJobListResponse,
    LanguageDetectionJobResponse,
    LanguageDetectionQueuedResponse,
    LanguageDetectionRunResponse,
    LanguageJobDocumentReference,
    LanguageJobFileReference,
    LanguageJobRequesterReference,
    LanguageJobRevisionReference,
    LanguagePresenceResponse,
    LanguageSummaryResponse,
)
from app.schemas.language_internal import CoverageBreakdownData
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
)
from app.services.language.language_detector_factory import (
    LanguageDetectorFactory,
)
from app.services.language.language_normalizer import (
    calculate_source_snapshot_hash,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.utils.datetime import utc_now


def language_job_not_found() -> Exception:
    return document_error(
        "The language detection job does not exist or is outside your scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Language detection job was not found.",
    )


def language_run_not_found() -> Exception:
    return document_error(
        "The language result does not exist or is outside your scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Language detection result was not found.",
    )


def language_file_not_found() -> Exception:
    return document_error(
        "The document file does not exist or is outside your scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Document file was not found.",
    )


class LanguageDetectionJobService(DocumentServiceBase):
    """Queue, list, inspect, re-run, and cancel language analysis."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
        *,
        model_ready: bool | None = None,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.config = LanguageRuntimeConfig.from_settings(settings)
        self.jobs = LanguageDetectionJobRepository(session)
        self.runs = LanguageDetectionRunRepository(session)
        self.extraction_runs = ExtractionRunRepository(session)
        self.ocr_runs = OCRRunRepository(session)
        self.files = DocumentFileRepository(session)
        self._model_ready_override = model_ready

    async def start(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID,
        ocr_run_id: UUID | None,
        force: bool,
    ) -> LanguageDetectionQueuedResponse:
        permission = (
            Permission.DOCUMENTS_REDETECT_LANGUAGE
            if force
            else Permission.DOCUMENTS_DETECT_LANGUAGE
        )
        self._ensure_permission(permission)
        return await self._queue(
            document_file_id=document_file_id,
            extraction_run_id=extraction_run_id,
            ocr_run_id=ocr_run_id,
            force=force,
            reason=None,
            job_type=(
                LanguageDetectionJobType.RE_DETECTION
                if force
                else LanguageDetectionJobType.INITIAL_DETECTION
            ),
        )

    async def redetect(
        self,
        run_id: UUID,
        *,
        reason: str,
    ) -> LanguageDetectionQueuedResponse:
        self._ensure_permission(Permission.DOCUMENTS_REDETECT_LANGUAGE)
        old_run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(old_run)
        assert old_run is not None
        latest_extraction = await self.extraction_runs.get_latest_by_file(
            old_run.document_file_id
        )
        if latest_extraction is None:
            raise document_error(
                "The current extraction source is unavailable.",
                title="Language re-detection could not be queued.",
            )
        latest_ocr = await self.ocr_runs.get_latest_by_file(
            old_run.document_file_id
        )
        if (
            latest_ocr is not None
            and latest_ocr.source_extraction_run_id
            != latest_extraction.id
        ):
            latest_ocr = None
        return await self._queue(
            document_file_id=old_run.document_file_id,
            extraction_run_id=latest_extraction.id,
            ocr_run_id=latest_ocr.id if latest_ocr is not None else None,
            force=True,
            reason=reason,
            job_type=LanguageDetectionJobType.RE_DETECTION,
        )

    async def _queue(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID,
        ocr_run_id: UUID | None,
        force: bool,
        reason: str | None,
        job_type: LanguageDetectionJobType,
    ) -> LanguageDetectionQueuedResponse:
        self._ensure_model_ready()
        document_file = await self._available_file(
            document_file_id,
            for_update=True,
        )
        extraction_run = await self.extraction_runs.get_by_id(
            extraction_run_id
        )
        if (
            extraction_run is None
            or extraction_run.document_file_id != document_file.id
            or document_file.latest_extraction_run_id != extraction_run.id
        ):
            raise document_error(
                "The selected extraction run is not the latest source for this file.",
                field="extractionRunId",
                title="Language source is not available.",
            )
        if extraction_run.status not in {
            ExtractionRunStatus.COMPLETED,
            ExtractionRunStatus.PARTIALLY_COMPLETED,
            ExtractionRunStatus.OCR_REQUIRED,
        }:
            raise document_error(
                "The selected extraction run has not produced usable content.",
                field="extractionRunId",
                title="Language source is not available.",
            )
        ocr_run: OCRRun | None = None
        if ocr_run_id is not None:
            ocr_run = await self.ocr_runs.get_by_id(ocr_run_id)
            if (
                ocr_run is None
                or ocr_run.document_file_id != document_file.id
                or ocr_run.source_extraction_run_id != extraction_run.id
                or document_file.latest_ocr_run_id != ocr_run.id
                or ocr_run.status
                not in {
                    OCRRunStatus.COMPLETED,
                    OCRRunStatus.PARTIALLY_COMPLETED,
                }
            ):
                raise document_error(
                    "The selected OCR run is not a usable source.",
                    field="ocrRunId",
                    title="Language source is not available.",
                )
        if (
            extraction_run.status is ExtractionRunStatus.OCR_REQUIRED
            and ocr_run is None
        ):
            raise document_error(
                "A completed OCR run is required for this scanned extraction.",
                field="ocrRunId",
                title="Language source is not available.",
            )
        native_count = int(
            await self.session.scalar(
                select(func.count(ExtractedBlock.id)).where(
                    ExtractedBlock.extraction_run_id == extraction_run.id
                )
            )
            or 0
        )
        ocr_count = (
            int(
                await self.session.scalar(
                    select(func.count(OCRBlock.id)).where(
                        OCRBlock.ocr_run_id == ocr_run.id
                    )
                )
                or 0
            )
            if ocr_run is not None
            else 0
        )
        if native_count + ocr_count == 0:
            raise document_error(
                "No extracted or OCR text is available for detection.",
                title="Language source is not available.",
            )
        if native_count + ocr_count > self.config.maximum_blocks:
            raise document_error(
                "Merged content exceeds the configured block limit.",
                title="Language source is too large.",
            )
        active = await self.jobs.find_active_by_file(
            document_file.id,
            for_update=True,
        )
        if active is not None:
            raise document_conflict(
                "An active language detection job already exists.",
                field="documentFileId",
                title="Active language detection already exists.",
            )
        source_hash = calculate_source_snapshot_hash(
            extraction_run.content_hash,
            ocr_run.content_hash if ocr_run is not None else None,
        )
        existing = await self.runs.find_by_source_hash(
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            source_content_hash=source_hash,
        )
        if existing is not None and not force:
            return LanguageDetectionQueuedResponse(
                job_id=existing.job_id,
                status=existing.job.status,
                progress=existing.job.progress,
                document_file_id=document_file.id,
                extraction_run_id=extraction_run.id,
                ocr_run_id=ocr_run.id if ocr_run is not None else None,
                reused_existing_result=True,
                run_id=existing.id,
            )
        maximum_retries = int(
            getattr(self.settings, "language_max_retries", 1)
        )
        job = LanguageDetectionJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            job_type=job_type,
            status=LanguageDetectionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            force=force,
            reason=reason,
            source_content_hash=source_hash,
            requested_by=self.user.id,
            maximum_attempts=maximum_retries + 1,
        )
        try:
            await self.jobs.create(job)
            await self.audit(
                action=(
                    AuditAction.REDETECT_LANGUAGE
                    if job_type is LanguageDetectionJobType.RE_DETECTION
                    else AuditAction.QUEUE_LANGUAGE_DETECTION
                ),
                entity_type="LanguageDetectionJob",
                entity_id=job.id,
                description=(
                    "Language re-detection queued."
                    if job_type is LanguageDetectionJobType.RE_DETECTION
                    else "Language detection queued."
                ),
                new_values={
                    "documentFileId": str(document_file.id),
                    "extractionRunId": str(extraction_run.id),
                    "ocrRunId": (
                        str(ocr_run.id) if ocr_run is not None else None
                    ),
                    "sourceContentHash": source_hash,
                    "reason": reason,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "An active language detection job already exists.",
                field="documentFileId",
                title="Active language detection already exists.",
            ) from exc
        await self._dispatch(job)
        return LanguageDetectionQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
        )

    async def get(self, job_id: UUID) -> LanguageDetectionJobResponse:
        self._ensure_any_view_permission()
        job = await self.jobs.get_by_id(job_id)
        self._ensure_job_access(job)
        assert job is not None
        return language_job_detail(job)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        document_id: UUID | None,
        revision_id: UUID | None,
        document_file_id: UUID | None,
        statuses: Sequence[LanguageDetectionJobStatus] | None,
        requested_by: UUID | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> LanguageDetectionJobListResponse:
        self._ensure_any_view_permission()
        items, total = await self.jobs.list(
            search=search,
            department_id=department_id,
            document_id=document_id,
            revision_id=revision_id,
            document_file_id=document_file_id,
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
        return LanguageDetectionJobListResponse(
            items=[language_job_item(job) for job in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def cancel(
        self,
        job_id: UUID,
    ) -> LanguageDetectionCancelResponse:
        self._ensure_permission(Permission.DOCUMENTS_DETECT_LANGUAGE)
        job = await self.jobs.get_by_id(job_id, for_update=True)
        self._ensure_job_access(job)
        assert job is not None
        if job.status not in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES:
            raise document_conflict(
                "Only an active language detection job can be cancelled.",
                title="Language detection cannot be cancelled.",
            )
        if (
            job.status
            is not LanguageDetectionJobStatus.CANCEL_REQUESTED
        ):
            await self.jobs.mark_cancel_requested(job)
            await self.audit(
                action=AuditAction.CANCEL_LANGUAGE_DETECTION,
                entity_type="LanguageDetectionJob",
                entity_id=job.id,
                description="Language detection cancellation requested.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "status": (
                        LanguageDetectionJobStatus.CANCEL_REQUESTED.value
                    ),
                },
            )
            await self.session.commit()
        return LanguageDetectionCancelResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            current_stage=job.current_stage,
            cancelled_at=job.cancelled_at,
        )

    async def _available_file(
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
            raise language_file_not_found()
        self.policy.ensure_document_access(document_file.document)
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
            or document_file.document.is_archived
        ):
            raise document_error(
                "Only a current available file may be analysed.",
                field="documentFileId",
                title="Language source is not available.",
            )
        return document_file

    async def _dispatch(self, job: LanguageDetectionJob) -> None:
        try:
            from app.workers.language_detection_tasks import (
                process_language_detection_job,
            )

            result = process_language_detection_job.apply_async(
                args=[str(job.id)],
                queue=getattr(
                    self.settings,
                    "language_queue_name",
                    "language",
                ),
            )
            job.worker_reference = str(result.id)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            fresh = await self.jobs.get_by_id(job.id, for_update=True)
            if fresh is not None:
                await self.jobs.mark_failed(
                    fresh,
                    failed_at=utc_now(),
                    error_code="LANGUAGE_DETECTION_FAILED",
                    error_message=(
                        "The language worker could not accept this job."
                    ),
                )
                await self.audit(
                    action=AuditAction.FAIL_LANGUAGE_DETECTION,
                    entity_type="LanguageDetectionJob",
                    entity_id=fresh.id,
                    description="Language detection dispatch failed.",
                    new_values={
                        "documentFileId": str(fresh.document_file_id),
                        "errorCode": "LANGUAGE_DETECTION_FAILED",
                    },
                )
                await self.session.commit()
            raise document_error(
                "The language worker is temporarily unavailable.",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="Language detection could not be queued.",
            ) from exc

    def _ensure_model_ready(self) -> None:
        ready = self._model_ready_override
        if ready is None:
            detector = LanguageDetectorFactory.create(self.settings)
            info = detector.get_detector_info()
            fasttext_info = info.get("fastText")
            ready = bool(
                isinstance(fasttext_info, dict)
                and fasttext_info.get("ready")
            )
        if not ready:
            raise document_error(
                "[LANGUAGE_MODEL_NOT_AVAILABLE] The local language model "
                "is not ready.",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="Language detection is unavailable.",
            )

    def _ensure_job_access(
        self,
        job: LanguageDetectionJob | None,
    ) -> None:
        if job is None:
            raise language_job_not_found()
        try:
            self.policy.ensure_document_access(job.document)
        except Exception as exc:
            raise language_job_not_found() from exc

    def _ensure_run_access(
        self,
        run: LanguageDetectionRun | None,
    ) -> None:
        if run is None:
            raise language_run_not_found()
        try:
            self.policy.ensure_document_access(run.document)
        except Exception as exc:
            raise language_run_not_found() from exc

    def _ensure_permission(self, permission: Permission | str) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()

    def _ensure_any_view_permission(self) -> None:
        if not any(
            has_permission(
                self.user.role,
                permission,
                is_superuser=self.user.is_superuser,
            )
            for permission in (
                Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                Permission.DOCUMENTS_DETECT_LANGUAGE,
            )
        ):
            raise AuthorizationError()


class LanguageResultService(DocumentServiceBase):
    """Department-scoped history, summary, block, and container reads."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.runs = LanguageDetectionRunRepository(session)
        self.blocks = LanguageBlockResultRepository(session)
        self.containers = LanguageContainerSummaryRepository(session)
        self.files = DocumentFileRepository(session)

    async def get_run(
        self,
        run_id: UUID,
    ) -> LanguageDetectionRunResponse:
        self._ensure_permission(Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS)
        run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(run)
        assert run is not None
        return await self._run_response(run)

    async def latest_for_file(
        self,
        file_id: UUID,
    ) -> LanguageDetectionRunResponse:
        self._ensure_permission(Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS)
        document_file = await self.files.get_by_id(file_id)
        self._ensure_file_access(document_file)
        run = await self.runs.get_latest_by_file(file_id)
        self._ensure_run_access(run)
        assert run is not None
        return await self._run_response(run, is_latest=True)

    async def history_for_file(
        self,
        file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> PaginationData[LanguageDetectionHistoryItem]:
        self._ensure_permission(Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS)
        document_file = await self.files.get_by_id(file_id)
        self._ensure_file_access(document_file)
        runs = await self.runs.list_by_file(
            file_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        total = await self.runs.count_by_file(file_id)
        latest = await self.runs.get_latest_by_file(file_id)
        return PaginationData(
            items=[
                language_history_item(
                    run,
                    is_latest=latest is not None and latest.id == run.id,
                )
                for run in runs
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def summary(
        self,
        run_id: UUID,
    ) -> LanguageSummaryResponse:
        response = await self.get_run(run_id)
        return LanguageSummaryResponse(
            **response.model_dump(
                include=set(LanguageSummaryResponse.model_fields),
            )
        )

    async def list_blocks(
        self,
        run_id: UUID,
        *,
        language_code: LanguageCode | None,
        source_type: LanguageSourceType | None,
        container_id: UUID | None,
        minimum_confidence: float | None,
        maximum_confidence: float | None,
        is_mixed: bool | None,
        eligibility_status: LanguageEligibilityStatus | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> LanguageBlockResultListResponse:
        run = await self._scoped_run(run_id)
        rows, total = await self.blocks.list(
            run.id,
            language_code=language_code,
            source_type=source_type,
            container_id=container_id,
            minimum_confidence=minimum_confidence,
            maximum_confidence=maximum_confidence,
            is_mixed=is_mixed,
            eligibility_status=eligibility_status,
            search=search,
            page=page,
            page_size=page_size,
        )
        return LanguageBlockResultListResponse(
            items=[language_block_response(row) for row in rows],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_containers(
        self,
        run_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> LanguageContainerSummaryListResponse:
        run = await self._scoped_run(run_id)
        items, total = await self.containers.list(
            run.id,
            page=page,
            page_size=page_size,
        )
        return LanguageContainerSummaryListResponse(
            items=[
                language_container_response(item) for item in items
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def _scoped_run(
        self,
        run_id: UUID,
    ) -> LanguageDetectionRun:
        self._ensure_permission(Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS)
        run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(run)
        assert run is not None
        return run

    async def _run_response(
        self,
        run: LanguageDetectionRun,
        *,
        is_latest: bool | None = None,
    ) -> LanguageDetectionRunResponse:
        if is_latest is None:
            latest = await self.runs.get_latest_by_file(
                run.document_file_id
            )
            is_latest = latest is not None and latest.id == run.id
        summary = language_summary_response(run)
        return LanguageDetectionRunResponse(
            **summary.model_dump(),
            document_file_id=run.document_file_id,
            document_id=run.document_id,
            document_revision_id=run.document_revision_id,
            extraction_run_id=run.extraction_run_id,
            ocr_run_id=run.ocr_run_id,
            job_id=run.job_id,
            detector_name=run.detector_name,
            detector_version=run.detector_version,
            status=run.status,
            source_content_hash=run.source_content_hash,
            warnings=_warning_strings(run.warnings_json),
            metadata=run.metadata_json,
            requested_by=(
                LanguageJobRequesterReference(
                    id=run.requester.id,
                    name=run.requester.name,
                )
                if run.requester is not None
                else None
            ),
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            is_latest=is_latest,
        )

    def _ensure_file_access(
        self,
        document_file: DocumentFile | None,
    ) -> None:
        if document_file is None:
            raise language_file_not_found()
        try:
            self.policy.ensure_document_access(document_file.document)
        except Exception as exc:
            raise language_file_not_found() from exc

    def _ensure_run_access(
        self,
        run: LanguageDetectionRun | None,
    ) -> None:
        if run is None:
            raise language_run_not_found()
        try:
            self.policy.ensure_document_access(run.document)
        except Exception as exc:
            raise language_run_not_found() from exc

    def _ensure_permission(self, permission: Permission | str) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()


def language_job_item(
    job: LanguageDetectionJob,
) -> LanguageDetectionJobListItem:
    return LanguageDetectionJobListItem(
        id=job.id,
        document=LanguageJobDocumentReference(
            id=job.document.id,
            base_document_code=job.document.base_document_code,
            title=job.document.title,
            department_id=job.document.department_id,
        ),
        revision=LanguageJobRevisionReference(
            id=job.revision.id,
            revision_code=job.revision.revision_code,
            full_document_code=job.revision.full_document_code,
        ),
        file=LanguageJobFileReference(
            id=job.document_file.id,
            filename=job.document_file.original_filename,
            extension=job.document_file.file_extension,
            sha256_hash=job.document_file.sha256_hash,
        ),
        extraction_run_id=job.extraction_run_id,
        ocr_run_id=job.ocr_run_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        requested_by=(
            LanguageJobRequesterReference(
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
            job.detection_run.id
            if job.detection_run is not None
            else None
        ),
        result_summary=job.result_summary_json,
    )


def language_job_detail(
    job: LanguageDetectionJob,
) -> LanguageDetectionJobResponse:
    item = language_job_item(job)
    return LanguageDetectionJobResponse(
        **item.model_dump(),
        attempt_number=job.attempt_number,
        maximum_attempts=job.maximum_attempts,
        failed_at=job.failed_at,
        error=(
            LanguageDetectionJobError(
                code=job.error_code,
                message=job.error_message
                or "Language detection failed.",
            )
            if job.error_code is not None
            else None
        ),
    )


def language_summary_response(
    run: LanguageDetectionRun,
) -> LanguageSummaryResponse:
    metadata = run.metadata_json or {}
    raw_coverage = metadata.get("coverage")
    coverage = raw_coverage if isinstance(raw_coverage, dict) else {}
    block_coverage = coverage.get("blockCoverage")
    character_coverage = coverage.get("characterCoverage")
    presence = coverage.get("languagePresence")
    zero_coverage = {
        "id": 0.0,
        "en": 0.0,
        "zh": 0.0,
        "mixed": 0.0,
        "unknown": 0.0,
        "other": 0.0,
    }
    return LanguageSummaryResponse(
        run_id=run.id,
        total_blocks=run.total_blocks,
        eligible_blocks=run.eligible_blocks,
        detected_blocks=run.detected_blocks,
        unknown_blocks=run.unknown_blocks,
        mixed_blocks=run.mixed_blocks,
        indonesian_blocks=run.indonesian_blocks,
        english_blocks=run.english_blocks,
        chinese_blocks=run.chinese_blocks,
        other_blocks=run.other_blocks,
        total_characters=run.total_characters,
        indonesian_characters=run.indonesian_characters,
        english_characters=run.english_characters,
        chinese_characters=run.chinese_characters,
        mixed_characters=run.mixed_characters,
        unknown_characters=run.unknown_characters,
        average_confidence=(
            float(run.average_confidence)
            if run.average_confidence is not None
            else None
        ),
        language_presence=LanguagePresenceResponse.model_validate(
            presence
            if isinstance(presence, dict)
            else {
                "id": "INSUFFICIENT_EVIDENCE",
                "en": "INSUFFICIENT_EVIDENCE",
                "zh": "INSUFFICIENT_EVIDENCE",
            }
        ),
        coverage=LanguageCoverageResponse(
            block_coverage=CoverageBreakdownData.model_validate(
                block_coverage
                if isinstance(block_coverage, dict)
                else zero_coverage
            ),
            character_coverage=CoverageBreakdownData.model_validate(
                character_coverage
                if isinstance(character_coverage, dict)
                else zero_coverage
            ),
            preliminary=True,
        ),
    )


def language_history_item(
    run: LanguageDetectionRun,
    *,
    is_latest: bool,
) -> LanguageDetectionHistoryItem:
    return LanguageDetectionHistoryItem(
        id=run.id,
        job_id=run.job_id,
        detector_name=run.detector_name,
        detector_version=run.detector_version,
        status=run.status,
        source_content_hash=run.source_content_hash,
        total_blocks=run.total_blocks,
        detected_blocks=run.detected_blocks,
        unknown_blocks=run.unknown_blocks,
        average_confidence=(
            float(run.average_confidence)
            if run.average_confidence is not None
            else None
        ),
        requested_by=(
            LanguageJobRequesterReference(
                id=run.requester.id,
                name=run.requester.name,
            )
            if run.requester is not None
            else None
        ),
        redetection_reason=run.job.reason,
        completed_at=run.completed_at,
        is_latest=is_latest,
    )


def language_block_response(
    row: LanguageBlockReadRow,
) -> LanguageBlockResultResponse:
    result = row.result
    return LanguageBlockResultResponse(
        id=result.id,
        extracted_block_id=result.extracted_block_id,
        ocr_block_id=result.ocr_block_id,
        container_id=result.container_id,
        source_type=result.source_type,
        source_reference=result.source_reference,
        text=row.text,
        language_code=result.language_code,
        primary_language_code=result.primary_language_code,
        confidence=float(result.confidence),
        is_mixed=result.is_mixed,
        detected_languages=list(result.detected_languages_json),
        script_statistics=dict(result.script_statistics_json),
        eligibility_status=result.eligibility_status,
        eligibility_reason=result.eligibility_reason,
        character_count=result.character_count,
        latin_character_count=result.latin_character_count,
        han_character_count=result.han_character_count,
        word_count=result.word_count,
        source_confidence=row.source_confidence,
        metadata=result.metadata_json,
        created_at=result.created_at,
    )


def language_container_response(
    item: LanguageContainerSummary,
) -> LanguageContainerSummaryResponse:
    return LanguageContainerSummaryResponse(
        id=item.id,
        container_id=item.container_id,
        container_type=item.container_type,
        container_name=item.container_name,
        container_index=item.container_index,
        total_blocks=item.total_blocks,
        eligible_blocks=item.eligible_blocks,
        indonesian_blocks=item.indonesian_blocks,
        english_blocks=item.english_blocks,
        chinese_blocks=item.chinese_blocks,
        mixed_blocks=item.mixed_blocks,
        unknown_blocks=item.unknown_blocks,
        other_blocks=item.other_blocks,
        indonesian_characters=item.indonesian_characters,
        english_characters=item.english_characters,
        chinese_characters=item.chinese_characters,
        mixed_characters=item.mixed_characters,
        unknown_characters=item.unknown_characters,
        dominant_language=item.dominant_language,
        language_presence=dict(item.language_presence_json),
        coverage=dict(item.coverage_json),
        created_at=item.created_at,
    )


def _warning_strings(
    warnings: list[str] | list[dict[str, object]],
) -> list[str]:
    values: list[str] = []
    for warning in warnings:
        if isinstance(warning, str):
            values.append(warning)
        elif isinstance(warning, dict):
            value = warning.get("code") or warning.get("message")
            if isinstance(value, str):
                values.append(value)
    return values
