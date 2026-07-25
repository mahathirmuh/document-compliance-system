"""Worker-side OCR orchestration with per-page transactions and cleanup."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.core.authorization import AuditAction
from app.core.config import Settings, get_settings
from app.database.session import AsyncSessionFactory
from app.models.document_file import DocumentFileStatus
from app.models.ocr_job import (
    ACTIVE_OCR_JOB_STATUSES,
    OCRJob,
    OCRJobStatus,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.ocr_job_repository import OCRJobRepository
from app.repositories.ocr_run_repository import OCRRunRepository
from app.services.extraction.extraction_cleanup_service import (
    ExtractionCleanupService,
)
from app.services.ocr.base_ocr_provider import (
    BaseOCRProvider,
    OCRCancelledError,
    OCRError,
    OCRProviderUnavailableError,
)
from app.services.ocr.ocr_page_service import OCRPageService
from app.services.ocr.ocr_persistence_service import OCRPersistenceService
from app.services.ocr.ocr_preprocessing_service import (
    OCRPreprocessingService,
)
from app.services.ocr.ocr_provider_factory import get_ocr_provider
from app.services.ocr.ocr_render_service import OCRRenderService
from app.services.ocr.ocr_temporary_cleanup_service import (
    OCRTemporaryCleanupService,
)
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_factory import get_storage
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class TransientOCRWorkerError(Exception):
    """Infrastructure failure eligible for bounded Celery retry."""


@dataclass(frozen=True, slots=True)
class PreparedOCRSource:
    document_file_id: UUID
    storage_key: str
    file_size: int
    sha256_hash: str
    run_id: UUID
    page_numbers: tuple[int, ...]
    language_profile: OCRLanguageProfile
    preprocessing_profile: OCRPreprocessingProfile


class OCRService:
    """Run local OCR without retaining DB sessions during recognition."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        storage: BaseStorage | None = None,
        provider: BaseOCRProvider | None = None,
        temporary_cleanup: OCRTemporaryCleanupService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or AsyncSessionFactory
        self.storage = storage or get_storage(self.settings)
        self.provider = provider or get_ocr_provider(self.settings)
        self.temporary_cleanup = temporary_cleanup or OCRTemporaryCleanupService()

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None = None,
        attempt_number: int = 1,
    ) -> OCRJobStatus:
        """Serialize duplicate at-least-once deliveries by job UUID."""
        async with self._execution_lock(job_id):
            return await self._process_claimed_job(
                job_id,
                worker_reference=worker_reference,
                attempt_number=attempt_number,
            )

    async def _process_claimed_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None,
        attempt_number: int,
    ) -> OCRJobStatus:
        temporary_directory: Path | None = None
        local_path: Path | None = None
        try:
            await self.temporary_cleanup.cleanup_stale(
                int(self.settings.ocr_temp_image_retention_hours)
            )
            prepared = await self._prepare_job(
                job_id,
                worker_reference=worker_reference,
                attempt_number=attempt_number,
            )
            if isinstance(prepared, OCRJobStatus):
                return prepared
            temporary_directory = Path(tempfile.mkdtemp(prefix="document-ocr-"))
            local_path = temporary_directory / "source.pdf"
            await self._copy_source(prepared, local_path)
            persisted_pages = await self._persisted_pages(prepared.run_id)
            pages_to_process = [
                page for page in prepared.page_numbers if page not in persisted_pages
            ]
            page_service = self._page_service()
            total_pages = len(prepared.page_numbers)
            for page_number in pages_to_process:
                if await self._is_cancel_requested(job_id):
                    raise OCRCancelledError
                page_index = prepared.page_numbers.index(page_number)
                base_progress = 10 + int(75 * page_index / max(1, total_pages))

                async def report(
                    stage: str,
                    *,
                    base_progress: int = base_progress,
                    page_index: int = page_index,
                ) -> None:
                    status = (
                        OCRJobStatus.RENDERING
                        if stage.startswith("Rendering")
                        else (
                            OCRJobStatus.PREPROCESSING
                            if stage.startswith("Preprocessing")
                            else OCRJobStatus.RECOGNISING
                        )
                    )
                    increment = {
                        OCRJobStatus.RENDERING: 0,
                        OCRJobStatus.PREPROCESSING: 3,
                        OCRJobStatus.RECOGNISING: 6,
                    }[status]
                    await self._set_status(
                        job_id,
                        status=status,
                        progress=min(84, base_progress + increment),
                        stage=(f"{stage} ({page_index + 1} of {total_pages})"),
                    )

                try:
                    result = await page_service.process_page(
                        local_path,
                        page_number,
                        temporary_directory,
                        language_profile=prepared.language_profile,
                        preprocessing_profile=(prepared.preprocessing_profile),
                        cancellation_checker=(
                            lambda: self._is_cancel_requested(job_id)
                        ),
                        stage_callback=report,
                    )
                except OCRProviderUnavailableError:
                    raise
                except OCRError as exc:
                    result = page_service.failed_page_result(
                        page_number,
                        prepared.language_profile,
                        0,
                        0,
                        int(
                            getattr(
                                self.settings,
                                "ocr_render_dpi",
                                300,
                            )
                        ),
                        exc,
                    )
                if await self._is_cancel_requested(job_id):
                    raise OCRCancelledError
                await self._persist_page(
                    job_id,
                    prepared.run_id,
                    result,
                    progress=min(
                        84,
                        10 + int(75 * (page_index + 1) / max(1, total_pages)),
                    ),
                )

            await self._set_status(
                job_id,
                status=OCRJobStatus.MERGING,
                progress=85,
                stage="Merging OCR provenance with extracted content",
            )
            if await self._is_cancel_requested(job_id):
                raise OCRCancelledError
            await self._set_status(
                job_id,
                status=OCRJobStatus.PERSISTING,
                progress=95,
                stage="Finalising OCR result",
            )
            return await self._finalize(
                job_id,
                prepared.run_id,
                cancelled=False,
            )
        except OCRCancelledError:
            return await self._cancel_job(job_id)
        except OCRProviderUnavailableError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.safe_message,
                error_details=exc.details,
            )
            return OCRJobStatus.FAILED
        except OCRError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.safe_message,
                error_details=exc.details,
            )
            return OCRJobStatus.FAILED
        except (OperationalError, ConnectionError, TimeoutError) as exc:
            raise TransientOCRWorkerError(
                "A temporary OCR infrastructure error occurred."
            ) from exc
        except SQLAlchemyError:
            logger.exception(
                "OCR persistence failed for job %s.",
                job_id,
            )
            await self.fail_job(
                job_id,
                error_code="OCR_PERSISTENCE_FAILED",
                error_message="The OCR result could not be saved.",
            )
            return OCRJobStatus.FAILED
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception("Unexpected OCR worker error for job %s.", job_id)
            await self.fail_job(
                job_id,
                error_code="OCR_RECOGNITION_FAILED",
                error_message="The OCR worker could not process the PDF.",
            )
            return OCRJobStatus.FAILED
        finally:
            if local_path is not None:
                await ExtractionCleanupService.remove_file(local_path)
            if temporary_directory is not None:
                await self.temporary_cleanup.remove_work_directory(temporary_directory)

    async def fail_job(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        error_details: dict[str, object] | None = None,
    ) -> None:
        try:
            async with self.session_factory() as session:
                jobs = OCRJobRepository(session)
                job = await jobs.get_by_id(job_id, for_update=True)
                if job is None or job.status not in ACTIVE_OCR_JOB_STATUSES:
                    return
                if job.status is OCRJobStatus.CANCEL_REQUESTED:
                    await self._mark_cancelled(session, job)
                else:
                    if job.ocr_run is not None:
                        await OCRPersistenceService(
                            session,
                            block_batch_size=self._batch_size,
                            low_confidence_threshold=self._low_confidence_threshold,
                            review_confidence_threshold=self._review_confidence_threshold,
                        ).finalize(
                            job=job,
                            run=job.ocr_run,
                            completed_at=utc_now(),
                            terminal_failure=True,
                        )
                    await jobs.mark_failed(
                        job,
                        failed_at=utc_now(),
                        error_code=error_code,
                        error_message=error_message,
                        error_details=error_details,
                    )
                    await AuditLogRepository(session).create(
                        user_id=job.requested_by,
                        action=AuditAction.FAIL_OCR,
                        entity_type="OCRJob",
                        entity_id=job.id,
                        description="Document OCR failed.",
                        new_values={
                            "documentFileId": str(job.document_file_id),
                            "errorCode": error_code,
                        },
                    )
                await session.commit()
        except SQLAlchemyError:
            return

    @asynccontextmanager
    async def _execution_lock(
        self,
        job_id: UUID,
    ) -> AsyncIterator[None]:
        bind = self.session_factory.kw.get("bind")
        if not isinstance(bind, AsyncEngine) or bind.dialect.name != "postgresql":
            yield
            return
        lock_key = job_id.int & ((1 << 63) - 1)
        async with bind.connect() as connection:
            await connection.execute(
                text("SELECT pg_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            )
            try:
                yield
            finally:
                try:
                    await asyncio.shield(
                        connection.execute(
                            text("SELECT pg_advisory_unlock(:lock_key)"),
                            {"lock_key": lock_key},
                        )
                    )
                except SQLAlchemyError:
                    logger.exception(
                        "Failed to release OCR advisory lock for %s.",
                        job_id,
                    )

    async def _prepare_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None,
        attempt_number: int,
    ) -> PreparedOCRSource | OCRJobStatus:
        async with self.session_factory() as session:
            jobs = OCRJobRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            if job is None:
                raise OCRError(
                    "OCR_PAGE_FAILED",
                    "The OCR job no longer exists.",
                )
            if job.status in {
                OCRJobStatus.COMPLETED,
                OCRJobStatus.PARTIALLY_COMPLETED,
                OCRJobStatus.FAILED,
                OCRJobStatus.CANCELLED,
            }:
                return job.status
            if job.status is OCRJobStatus.CANCEL_REQUESTED:
                await self._mark_cancelled(session, job)
                await session.commit()
                return OCRJobStatus.CANCELLED
            document_file = job.document_file
            if (
                document_file.file_status is not DocumentFileStatus.AVAILABLE
                or not document_file.is_current
                or document_file.file_extension.lower() != "pdf"
                or document_file.document_id != job.document_id
                or document_file.document_revision_id != job.document_revision_id
                or job.document.is_archived
                or job.extraction_run.document_file_id != document_file.id
            ):
                raise OCRError(
                    "OCR_FILE_NOT_AVAILABLE",
                    "The source PDF is no longer available.",
                )
            job.attempt_number = min(
                max(1, attempt_number),
                job.maximum_attempts,
            )
            job.worker_reference = worker_reference
            started_at = job.started_at or utc_now()
            await jobs.update_status(
                job,
                status=OCRJobStatus.INSPECTING,
                progress=5,
                current_stage="Inspecting PDF OCR source",
                started_at=started_at,
            )
            provider_info = self.provider.get_provider_info()
            run = await OCRPersistenceService(
                session,
                block_batch_size=self._batch_size,
                low_confidence_threshold=self._low_confidence_threshold,
                review_confidence_threshold=self._review_confidence_threshold,
            ).create_or_get_run(
                job=job,
                document_file=document_file,
                provider_version=(
                    str(provider_info["version"])
                    if provider_info.get("version")
                    else None
                ),
                render_dpi=int(getattr(self.settings, "ocr_render_dpi", 300)),
                started_at=started_at,
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.START_OCR,
                entity_type="OCRJob",
                entity_id=job.id,
                description="Document OCR worker started.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "attemptNumber": job.attempt_number,
                    "pageNumbers": job.requested_page_numbers_json,
                },
            )
            await session.commit()
            return PreparedOCRSource(
                document_file_id=document_file.id,
                storage_key=document_file.storage_key,
                file_size=document_file.file_size,
                sha256_hash=document_file.sha256_hash,
                run_id=run.id,
                page_numbers=tuple(job.requested_page_numbers_json),
                language_profile=job.language_profile,
                preprocessing_profile=job.preprocessing_profile,
            )

    async def _copy_source(
        self,
        source_data: PreparedOCRSource,
        destination: Path,
    ) -> None:
        try:
            source = await self.storage.open(source_data.storage_key)
        except FileNotFoundError as exc:
            raise OCRError(
                "OCR_FILE_NOT_AVAILABLE",
                "The source PDF could not be found in private storage.",
            ) from exc
        try:
            actual_size, actual_hash = await asyncio.to_thread(
                _copy_and_hash,
                source,
                destination,
                int(
                    getattr(
                        self.settings,
                        "extraction_max_file_size_mb",
                        50,
                    )
                )
                * 1024
                * 1024,
            )
        finally:
            await asyncio.to_thread(source.close)
        if (
            actual_size != source_data.file_size
            or actual_hash != source_data.sha256_hash
        ):
            await ExtractionCleanupService.remove_file(destination)
            raise OCRError(
                "OCR_FILE_NOT_AVAILABLE",
                "The source PDF failed its integrity check.",
            )

    async def _persist_page(
        self,
        job_id: UUID,
        run_id: UUID,
        result: object,
        *,
        progress: int,
    ) -> None:
        from app.schemas.ocr_internal import OCRPageResult

        if not isinstance(result, OCRPageResult):
            raise OCRError(
                "OCR_PERSISTENCE_FAILED",
                "The OCR provider returned an invalid page result.",
            )
        async with self.session_factory() as session:
            jobs = OCRJobRepository(session)
            runs = OCRRunRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            run = await runs.get_by_id(run_id, for_update=True)
            if job is None or run is None:
                raise OCRError(
                    "OCR_PERSISTENCE_FAILED",
                    "The OCR job result no longer exists.",
                )
            if job.status is OCRJobStatus.CANCEL_REQUESTED:
                raise OCRCancelledError
            persistence = OCRPersistenceService(
                session,
                block_batch_size=self._batch_size,
                low_confidence_threshold=self._low_confidence_threshold,
                review_confidence_threshold=self._review_confidence_threshold,
            )
            await persistence.persist_page(run, result)
            if result.status.value == "FAILED":
                job.failed_page_numbers_json = sorted(
                    {
                        *job.failed_page_numbers_json,
                        result.page_number,
                    }
                )
            else:
                job.processed_page_numbers_json = sorted(
                    {
                        *job.processed_page_numbers_json,
                        result.page_number,
                    }
                )
            await jobs.update_status(
                job,
                status=OCRJobStatus.PERSISTING,
                progress=progress,
                current_stage=f"Persisted OCR page {result.page_number}",
            )
            await session.commit()

    async def _finalize(
        self,
        job_id: UUID,
        run_id: UUID,
        *,
        cancelled: bool,
    ) -> OCRJobStatus:
        async with self.session_factory() as session:
            jobs = OCRJobRepository(session)
            runs = OCRRunRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            run = await runs.get_by_id(run_id, for_update=True)
            if job is None or run is None:
                raise OCRError(
                    "OCR_PERSISTENCE_FAILED",
                    "The OCR result could not be finalized.",
                )
            await OCRPersistenceService(
                session,
                block_batch_size=self._batch_size,
                low_confidence_threshold=self._low_confidence_threshold,
                review_confidence_threshold=self._review_confidence_threshold,
            ).finalize(
                job=job,
                run=run,
                completed_at=utc_now(),
                cancelled=cancelled,
            )
            action = {
                OCRJobStatus.COMPLETED: AuditAction.COMPLETE_OCR,
                OCRJobStatus.PARTIALLY_COMPLETED: AuditAction.PARTIAL_OCR,
                OCRJobStatus.CANCELLED: AuditAction.CANCEL_OCR,
                OCRJobStatus.FAILED: AuditAction.FAIL_OCR,
            }[job.status]
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=action,
                entity_type="OCRRun",
                entity_id=run.id,
                description=f"Document OCR {job.status.value.lower()}.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "runId": str(run.id),
                    "status": job.status.value,
                },
            )
            await session.commit()
            return job.status

    async def _cancel_job(self, job_id: UUID) -> OCRJobStatus:
        async with self.session_factory() as session:
            job = await OCRJobRepository(session).get_by_id(
                job_id,
                for_update=True,
            )
            if job is None:
                return OCRJobStatus.CANCELLED
            run_id = job.ocr_run.id if job.ocr_run is not None else None
        if run_id is not None:
            return await self._finalize(
                job_id,
                run_id,
                cancelled=True,
            )
        async with self.session_factory() as session:
            job = await OCRJobRepository(session).get_by_id(
                job_id,
                for_update=True,
            )
            if job is not None:
                await self._mark_cancelled(session, job)
                await session.commit()
        return OCRJobStatus.CANCELLED

    async def _set_status(
        self,
        job_id: UUID,
        *,
        status: OCRJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        async with self.session_factory() as session:
            repository = OCRJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if (
                job is None
                or job.status is OCRJobStatus.CANCEL_REQUESTED
                or job.status not in ACTIVE_OCR_JOB_STATUSES
            ):
                raise OCRCancelledError
            await repository.update_status(
                job,
                status=status,
                progress=progress,
                current_stage=stage,
            )
            await session.commit()

    async def _is_cancel_requested(self, job_id: UUID) -> bool:
        async with self.session_factory() as session:
            job = await OCRJobRepository(session).get_by_id(job_id)
            return (
                job is None
                or job.status is OCRJobStatus.CANCEL_REQUESTED
                or job.status is OCRJobStatus.CANCELLED
            )

    async def _persisted_pages(self, run_id: UUID) -> set[int]:
        async with self.session_factory() as session:
            return await OCRPersistenceService(
                session,
                block_batch_size=self._batch_size,
                low_confidence_threshold=self._low_confidence_threshold,
                review_confidence_threshold=self._review_confidence_threshold,
            ).persisted_page_numbers(run_id)

    def _page_service(self) -> OCRPageService:
        return OCRPageService(
            self.provider,
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
            provider_options={
                "auto_multilingual_chinese_pass": bool(
                    getattr(
                        self.settings,
                        "ocr_auto_multilingual_chinese_pass",
                        True,
                    )
                ),
                "chinese_pass_confidence_threshold": float(
                    getattr(
                        self.settings,
                        ("ocr_auto_multilingual_chinese_pass_confidence_threshold"),
                        0.65,
                    )
                ),
                "chinese_pass_minimum_characters": int(
                    getattr(
                        self.settings,
                        ("ocr_auto_multilingual_chinese_pass_minimum_characters"),
                        20,
                    )
                ),
            },
        )

    @property
    def _batch_size(self) -> int:
        return int(
            getattr(
                self.settings,
                "ocr_db_batch_size",
                getattr(self.settings, "extraction_db_batch_size", 1000),
            )
        )

    @property
    def _low_confidence_threshold(self) -> float:
        return float(getattr(self.settings, "ocr_low_confidence_threshold", 0.60))

    @property
    def _review_confidence_threshold(self) -> float:
        return float(getattr(self.settings, "ocr_review_confidence_threshold", 0.80))

    @staticmethod
    async def _mark_cancelled(
        session: AsyncSession,
        job: OCRJob,
    ) -> None:
        await OCRJobRepository(session).mark_cancelled(
            job,
            cancelled_at=utc_now(),
        )
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.CANCEL_OCR,
            entity_type="OCRJob",
            entity_id=job.id,
            description="Document OCR cancelled.",
            new_values={
                "documentFileId": str(job.document_file_id),
                "status": OCRJobStatus.CANCELLED.value,
            },
        )


def _copy_and_hash(
    source: BinaryIO,
    destination: Path,
    maximum_bytes: int,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    try:
        with destination.open("xb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum_bytes:
                    raise OCRError(
                        "OCR_FILE_NOT_AVAILABLE",
                        "The PDF exceeds the configured OCR file limit.",
                    )
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return total, digest.hexdigest()
