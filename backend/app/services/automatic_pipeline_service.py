"""Optional worker-side chaining for extraction, OCR, and language jobs."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import TypeAlias
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction
from app.core.config import Settings, get_settings
from app.database.session import AsyncSessionFactory
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extracted_block import ExtractedBlock
from app.models.extracted_container import ExtractedContainer
from app.models.extraction_job import ExtractionJobStatus
from app.models.extraction_run import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractorType,
)
from app.models.language_detection_job import (
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import (
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.repositories.audit_log import AuditLogRepository
from app.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from app.repositories.language_detection_job_repository import (
    LanguageDetectionJobRepository,
)
from app.repositories.ocr_job_repository import OCRJobRepository
from app.services.language.language_normalizer import (
    calculate_source_snapshot_hash,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.services.ocr.base_ocr_provider import OCRError
from app.services.ocr.ocr_page_service import OCRPageService
from app.services.ocr.ocr_preprocessing_service import (
    OCRPreprocessingService,
)
from app.services.ocr.ocr_provider_factory import get_ocr_provider
from app.services.ocr.ocr_render_service import OCRRenderService
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)

DispatchResult: TypeAlias = str | None
DispatchCallback: TypeAlias = Callable[
    [UUID],
    DispatchResult | Awaitable[DispatchResult],
]

_EXTRACTION_LANGUAGE_STATUSES = frozenset(
    {
        ExtractionJobStatus.COMPLETED,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
    }
)
_EXTRACTION_OCR_STATUSES = frozenset(
    {
        ExtractionJobStatus.OCR_REQUIRED,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
    }
)
_OCR_LANGUAGE_STATUSES = frozenset(
    {
        OCRJobStatus.COMPLETED,
        OCRJobStatus.PARTIALLY_COMPLETED,
    }
)


class AutomaticPipelineService:
    """Create configured downstream jobs without an HTTP request context.

    The source job's ``requested_by`` value is retained for attribution. A
    missing source user remains ``NULL`` rather than inventing a privileged
    system user. Database uniqueness remains the final race-condition guard.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        ocr_dispatcher: DispatchCallback | None = None,
        language_dispatcher: DispatchCallback | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or AsyncSessionFactory
        self.ocr_dispatcher = ocr_dispatcher
        self.language_dispatcher = language_dispatcher

    async def after_extraction(
        self,
        extraction_job_id: UUID,
        status: ExtractionJobStatus,
    ) -> UUID | None:
        """Queue at most one configured downstream job after extraction."""
        if (
            status in _EXTRACTION_OCR_STATUSES
            and self.settings.auto_run_ocr_after_extraction
        ):
            queued_ocr = await self._queue_ocr(extraction_job_id)
            if queued_ocr is not None:
                return queued_ocr
        if (
            status in _EXTRACTION_LANGUAGE_STATUSES
            and self.settings.auto_run_language_detection_after_extraction
        ):
            return await self._queue_language_from_extraction(extraction_job_id)
        return None

    async def after_ocr(
        self,
        ocr_job_id: UUID,
        status: OCRJobStatus,
    ) -> UUID | None:
        """Queue language detection after a usable OCR result when enabled."""
        if (
            status not in _OCR_LANGUAGE_STATUSES
            or not self.settings.auto_run_language_detection_after_ocr
        ):
            return None
        return await self._queue_language_from_ocr(ocr_job_id)

    async def _queue_ocr(
        self,
        extraction_job_id: UUID,
    ) -> UUID | None:
        job_id: UUID | None = None
        try:
            async with self.session_factory() as session:
                source = await ExtractionJobRepository(session).get_by_id(
                    extraction_job_id,
                    for_update=True,
                )
                if (
                    source is None
                    or source.status not in _EXTRACTION_OCR_STATUSES
                    or source.extraction_run is None
                ):
                    return None
                extraction_run = source.extraction_run
                document_file = source.document_file
                if not self._eligible_ocr_source(
                    extraction_run,
                    document_file,
                ):
                    return None

                jobs = OCRJobRepository(session)
                if (
                    await jobs.find_active_by_file(
                        document_file.id,
                        for_update=True,
                    )
                    is not None
                ):
                    return None
                if source.requested_by is not None:
                    await jobs.acquire_user_concurrency_lock(source.requested_by)
                    if (
                        await jobs.count_active_by_user(source.requested_by)
                        >= self.settings.ocr_max_concurrent_jobs_per_user
                    ):
                        return None
                completed = await session.scalar(
                    select(OCRRun.id)
                    .where(
                        OCRRun.document_file_id == document_file.id,
                        OCRRun.source_extraction_run_id == extraction_run.id,
                        OCRRun.status.in_(
                            {
                                OCRRunStatus.COMPLETED,
                                OCRRunStatus.PARTIALLY_COMPLETED,
                            }
                        ),
                    )
                    .limit(1)
                )
                if completed is not None:
                    return None

                containers = list(
                    await session.scalars(
                        select(ExtractedContainer)
                        .where(
                            ExtractedContainer.extraction_run_id == extraction_run.id
                        )
                        .order_by(ExtractedContainer.container_index)
                    )
                )
                selection = self._ocr_page_service().select_pages(
                    extraction_run,
                    containers,
                    requested_page_numbers=None,
                    force=False,
                )
                if not selection.selected_page_numbers:
                    return None

                provider_info = get_ocr_provider(self.settings).get_provider_info()
                job = OCRJob(
                    document_id=source.document_id,
                    document_revision_id=source.document_revision_id,
                    document_file_id=source.document_file_id,
                    extraction_run_id=extraction_run.id,
                    job_type=OCRJobType.INITIAL_OCR,
                    status=OCRJobStatus.QUEUED,
                    progress=0,
                    current_stage="Queued",
                    language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
                    preprocessing_profile=OCRPreprocessingProfile(
                        self.settings.ocr_default_preprocessing_profile
                    ),
                    requested_page_numbers_json=(selection.selected_page_numbers),
                    processed_page_numbers_json=[],
                    failed_page_numbers_json=[],
                    requested_by=source.requested_by,
                    maximum_attempts=self.settings.ocr_max_retries + 1,
                    provider=str(provider_info.get("name") or "paddleocr"),
                    provider_version=(
                        str(provider_info["version"])
                        if provider_info.get("version")
                        else None
                    ),
                    result_summary_json={
                        "pageSelection": selection.model_dump(
                            mode="json",
                            by_alias=True,
                        ),
                        "automaticPipeline": {
                            "trigger": "EXTRACTION_OCR_REQUIRED",
                            "sourceJobId": str(source.id),
                        },
                    },
                )
                try:
                    await jobs.create(job)
                    await AuditLogRepository(session).create(
                        user_id=source.requested_by,
                        action=AuditAction.QUEUE_OCR,
                        entity_type="OCRJob",
                        entity_id=job.id,
                        description=(
                            "Document OCR queued automatically after extraction."
                        ),
                        new_values={
                            "automatic": True,
                            "trigger": "EXTRACTION_OCR_REQUIRED",
                            "sourceJobId": str(source.id),
                            "documentFileId": str(document_file.id),
                            "extractionRunId": str(extraction_run.id),
                            "languageProfile": (
                                OCRLanguageProfile.AUTO_MULTILINGUAL.value
                            ),
                            "pageNumbers": (selection.selected_page_numbers),
                        },
                    )
                    await session.commit()
                    job_id = job.id
                except IntegrityError:
                    await session.rollback()
                    return None
        except OCRError:
            logger.warning(
                "Automatic OCR found no eligible pages for extraction job %s.",
                extraction_job_id,
            )
            return None

        if job_id is not None:
            await self._dispatch_ocr(job_id)
        return job_id

    async def _queue_language_from_extraction(
        self,
        extraction_job_id: UUID,
    ) -> UUID | None:
        async with self.session_factory() as session:
            source = await ExtractionJobRepository(session).get_by_id(
                extraction_job_id,
                for_update=True,
            )
            if (
                source is None
                or source.status not in _EXTRACTION_LANGUAGE_STATUSES
                or source.extraction_run is None
                or source.extraction_run.status
                not in {
                    ExtractionRunStatus.COMPLETED,
                    ExtractionRunStatus.PARTIALLY_COMPLETED,
                }
                or source.extraction_run.requires_ocr
            ):
                return None
            return await self._queue_language(
                session,
                extraction_run=source.extraction_run,
                ocr_run=None,
                requested_by=source.requested_by,
                trigger="EXTRACTION_COMPLETED",
                source_job_id=source.id,
            )

    async def _queue_language_from_ocr(
        self,
        ocr_job_id: UUID,
    ) -> UUID | None:
        async with self.session_factory() as session:
            source = await OCRJobRepository(session).get_by_id(
                ocr_job_id,
                for_update=True,
            )
            if (
                source is None
                or source.status not in _OCR_LANGUAGE_STATUSES
                or source.ocr_run is None
                or source.ocr_run.status
                not in {
                    OCRRunStatus.COMPLETED,
                    OCRRunStatus.PARTIALLY_COMPLETED,
                }
            ):
                return None
            return await self._queue_language(
                session,
                extraction_run=source.extraction_run,
                ocr_run=source.ocr_run,
                requested_by=source.requested_by,
                trigger="OCR_COMPLETED",
                source_job_id=source.id,
            )

    async def _queue_language(
        self,
        session: AsyncSession,
        *,
        extraction_run: ExtractionRun,
        ocr_run: OCRRun | None,
        requested_by: UUID | None,
        trigger: str,
        source_job_id: UUID,
    ) -> UUID | None:
        document_file = extraction_run.document_file
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
            or document_file.document.is_archived
            or document_file.latest_extraction_run_id != extraction_run.id
        ):
            return None
        if ocr_run is None and extraction_run.requires_ocr:
            return None
        if ocr_run is not None and (
            ocr_run.document_file_id != extraction_run.document_file_id
            or ocr_run.source_extraction_run_id != extraction_run.id
            or document_file.latest_ocr_run_id != ocr_run.id
        ):
            return None

        native_count = int(
            await session.scalar(
                select(func.count(ExtractedBlock.id)).where(
                    ExtractedBlock.extraction_run_id == extraction_run.id
                )
            )
            or 0
        )
        ocr_count = (
            int(
                await session.scalar(
                    select(func.count(OCRBlock.id)).where(
                        OCRBlock.ocr_run_id == ocr_run.id
                    )
                )
                or 0
            )
            if ocr_run is not None
            else 0
        )
        block_count = native_count + ocr_count
        if (
            block_count == 0
            or block_count
            > LanguageRuntimeConfig.from_settings(self.settings).maximum_blocks
        ):
            return None

        jobs = LanguageDetectionJobRepository(session)
        if (
            await jobs.find_active_by_file(
                extraction_run.document_file_id,
                for_update=True,
            )
            is not None
        ):
            return None

        source_hash = calculate_source_snapshot_hash(
            extraction_run.content_hash,
            ocr_run.content_hash if ocr_run is not None else None,
        )
        completed_query = select(LanguageDetectionRun.id).where(
            LanguageDetectionRun.document_file_id == extraction_run.document_file_id,
            LanguageDetectionRun.extraction_run_id == extraction_run.id,
            LanguageDetectionRun.source_content_hash == source_hash,
            LanguageDetectionRun.status.in_(
                {
                    LanguageDetectionRunStatus.COMPLETED,
                    LanguageDetectionRunStatus.PARTIALLY_COMPLETED,
                }
            ),
        )
        if ocr_run is None:
            completed_query = completed_query.where(
                LanguageDetectionRun.ocr_run_id.is_(None)
            )
        else:
            completed_query = completed_query.where(
                LanguageDetectionRun.ocr_run_id == ocr_run.id
            )
        if await session.scalar(completed_query.limit(1)) is not None:
            return None

        job = LanguageDetectionJob(
            document_id=extraction_run.document_id,
            document_revision_id=extraction_run.document_revision_id,
            document_file_id=extraction_run.document_file_id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            job_type=LanguageDetectionJobType.INITIAL_DETECTION,
            status=LanguageDetectionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            force=False,
            source_content_hash=source_hash,
            requested_by=requested_by,
            maximum_attempts=self.settings.language_max_retries + 1,
            result_summary_json={
                "automaticPipeline": {
                    "trigger": trigger,
                    "sourceJobId": str(source_job_id),
                }
            },
        )
        try:
            await jobs.create(job)
            await AuditLogRepository(session).create(
                user_id=requested_by,
                action=AuditAction.QUEUE_LANGUAGE_DETECTION,
                entity_type="LanguageDetectionJob",
                entity_id=job.id,
                description=(
                    "Language detection queued automatically after "
                    f"{'OCR' if ocr_run is not None else 'extraction'}."
                ),
                new_values={
                    "automatic": True,
                    "trigger": trigger,
                    "sourceJobId": str(source_job_id),
                    "documentFileId": str(extraction_run.document_file_id),
                    "extractionRunId": str(extraction_run.id),
                    "ocrRunId": (str(ocr_run.id) if ocr_run is not None else None),
                    "sourceContentHash": source_hash,
                },
            )
            await session.commit()
            job_id = job.id
        except IntegrityError:
            await session.rollback()
            return None

        await self._dispatch_language(job_id)
        return job_id

    async def _dispatch_ocr(self, job_id: UUID) -> None:
        try:
            worker_reference = await self._invoke_dispatcher(
                self.ocr_dispatcher or self._default_ocr_dispatcher,
                job_id,
            )
        except Exception:
            logger.exception(
                "Automatic OCR dispatch failed for job %s.",
                job_id,
            )
            await self._mark_ocr_dispatch_failed(job_id)
            return
        await self._store_worker_reference(
            job_id,
            worker_reference,
            ocr=True,
        )

    async def _dispatch_language(self, job_id: UUID) -> None:
        try:
            worker_reference = await self._invoke_dispatcher(
                self.language_dispatcher or self._default_language_dispatcher,
                job_id,
            )
        except Exception:
            logger.exception(
                "Automatic language dispatch failed for job %s.",
                job_id,
            )
            await self._mark_language_dispatch_failed(job_id)
            return
        await self._store_worker_reference(
            job_id,
            worker_reference,
            ocr=False,
        )

    async def _store_worker_reference(
        self,
        job_id: UUID,
        worker_reference: str | None,
        *,
        ocr: bool,
    ) -> None:
        if not worker_reference:
            return
        async with self.session_factory() as session:
            if ocr:
                job = await OCRJobRepository(session).get_by_id(
                    job_id,
                    for_update=True,
                )
                is_queued = job is not None and job.status is OCRJobStatus.QUEUED
            else:
                job = await LanguageDetectionJobRepository(session).get_by_id(
                    job_id, for_update=True
                )
                is_queued = (
                    job is not None and job.status is LanguageDetectionJobStatus.QUEUED
                )
            if job is not None and is_queued:
                job.worker_reference = worker_reference[:255]
                await session.commit()

    async def _mark_ocr_dispatch_failed(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            jobs = OCRJobRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            if job is None or job.status is not OCRJobStatus.QUEUED:
                return
            await jobs.mark_failed(
                job,
                failed_at=utc_now(),
                error_code="OCR_PROVIDER_UNAVAILABLE",
                error_message="The OCR worker could not accept this job.",
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.FAIL_OCR,
                entity_type="OCRJob",
                entity_id=job.id,
                description="Automatic OCR dispatch failed.",
                new_values={
                    "automatic": True,
                    "documentFileId": str(job.document_file_id),
                    "errorCode": "OCR_PROVIDER_UNAVAILABLE",
                },
            )
            await session.commit()

    async def _mark_language_dispatch_failed(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            jobs = LanguageDetectionJobRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            if job is None or job.status is not LanguageDetectionJobStatus.QUEUED:
                return
            await jobs.mark_failed(
                job,
                failed_at=utc_now(),
                error_code="LANGUAGE_DETECTION_FAILED",
                error_message=("The language worker could not accept this job."),
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.FAIL_LANGUAGE_DETECTION,
                entity_type="LanguageDetectionJob",
                entity_id=job.id,
                description="Automatic language dispatch failed.",
                new_values={
                    "automatic": True,
                    "documentFileId": str(job.document_file_id),
                    "errorCode": "LANGUAGE_DETECTION_FAILED",
                },
            )
            await session.commit()

    def _ocr_page_service(self) -> OCRPageService:
        return OCRPageService(
            get_ocr_provider(self.settings),
            OCRRenderService(
                dpi=self.settings.ocr_render_dpi,
                image_format=self.settings.ocr_render_format,
                maximum_width=self.settings.ocr_max_render_width,
                maximum_height=self.settings.ocr_max_render_height,
            ),
            OCRPreprocessingService(),
            selectable_text_minimum=(self.settings.ocr_selectable_text_min_characters),
            skip_pages_with_selectable_text=(
                self.settings.ocr_skip_pages_with_selectable_text
            ),
            maximum_pages=self.settings.ocr_max_pages_per_job,
            maximum_page_retries=self.settings.ocr_max_retries,
            low_confidence_threshold=(self.settings.ocr_low_confidence_threshold),
        )

    @staticmethod
    def _eligible_ocr_source(
        extraction_run: ExtractionRun,
        document_file: DocumentFile,
    ) -> bool:
        return bool(
            extraction_run.extractor_type is ExtractorType.PDF
            and extraction_run.status
            in {
                ExtractionRunStatus.OCR_REQUIRED,
                ExtractionRunStatus.PARTIALLY_COMPLETED,
            }
            and extraction_run.requires_ocr
            and document_file.file_extension.lower() == "pdf"
            and document_file.file_status is DocumentFileStatus.AVAILABLE
            and document_file.is_current
            and not document_file.document.is_archived
            and document_file.latest_extraction_run_id == extraction_run.id
        )

    @staticmethod
    async def _invoke_dispatcher(
        callback: DispatchCallback,
        job_id: UUID,
    ) -> DispatchResult:
        result = callback(job_id)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _default_ocr_dispatcher(self, job_id: UUID) -> str | None:
        from app.workers.ocr_tasks import process_ocr_job

        result = process_ocr_job.apply_async(
            args=[str(job_id)],
            queue=self.settings.ocr_queue_name,
        )
        return str(result.id) if result.id is not None else None

    def _default_language_dispatcher(
        self,
        job_id: UUID,
    ) -> str | None:
        from app.workers.language_detection_tasks import (
            process_language_detection_job,
        )

        result = process_language_detection_job.apply_async(
            args=[str(job_id)],
            queue=self.settings.language_queue_name,
        )
        return str(result.id) if result.id is not None else None
