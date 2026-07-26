"""Merged-source loading plus worker-side language detection orchestration."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.core.authorization import AuditAction
from app.core.config import Settings, get_settings
from app.database.session import AsyncSessionFactory
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.language_detection_job import (
    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES,
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
)
from app.models.ocr_run import OCRRunStatus
from app.repositories.audit_log import AuditLogRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.repositories.language_detection_job_repository import (
    LanguageDetectionJobRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.language_internal import (
    DetectedLanguageBlockData,
    LanguagePipelineResultData,
    LanguageSourceBlockData,
)
from app.services.language.base_language_detector import (
    BaseLanguageDetector,
    LanguageDetectorError,
)
from app.services.language.language_aggregation_service import (
    LanguageAggregationService,
)
from app.services.language.language_detector_factory import (
    LanguageDetectorFactory,
)
from app.services.language.language_normalizer import (
    calculate_source_snapshot_hash,
    normalize_language_text,
)
from app.services.language.language_persistence_service import (
    LanguagePersistenceService,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.services.ocr.ocr_source_chain_service import (
    OCRSourceChainError,
    OCRSourceChainService,
)
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class LanguagePipelineError(RuntimeError):
    """Stable language-pipeline failure safe to map onto a job."""

    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.details = details


class LanguageDetectionCancelledError(LanguagePipelineError):
    def __init__(self) -> None:
        super().__init__(
            "LANGUAGE_CANCELLED",
            "Language detection was cancelled.",
        )


class TransientLanguageWorkerError(RuntimeError):
    """Infrastructure failures that Celery may retry."""


@dataclass(frozen=True, slots=True)
class PreparedLanguageJob:
    extraction_run_id: UUID
    ocr_run_id: UUID | None
    source_content_hash: str


ProgressCallback = Callable[[int, int], Awaitable[None]]
CancellationChecker = Callable[[], Awaitable[bool]]


class LanguageDetectionService:
    """Execute one local-only job with short database transactions."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        detector: BaseLanguageDetector | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.config = LanguageRuntimeConfig.from_settings(self.settings)
        self.session_factory = session_factory or AsyncSessionFactory
        self.detector = detector or LanguageDetectorFactory.create(self.settings)
        self.aggregation = LanguageAggregationService(self.config)

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None = None,
        attempt_number: int = 1,
    ) -> LanguageDetectionJobStatus:
        """Serialize at-least-once delivery and retain exactly one run."""
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
    ) -> LanguageDetectionJobStatus:
        try:
            prepared = await self._prepare_job(
                job_id,
                worker_reference=worker_reference,
                attempt_number=attempt_number,
            )
            if isinstance(prepared, LanguageDetectionJobStatus):
                return prepared
            await self._set_status(
                job_id,
                status=LanguageDetectionJobStatus.LOADING_CONTENT,
                progress=8,
                stage="Loading merged native and OCR content",
            )
            sources = await self._load_sources(
                prepared.extraction_run_id,
                prepared.ocr_run_id,
            )
            if not sources:
                raise LanguagePipelineError(
                    "LANGUAGE_SOURCE_NOT_AVAILABLE",
                    "No extracted or OCR text is available for detection.",
                )
            if await self._is_cancel_requested(job_id):
                raise LanguageDetectionCancelledError
            await self._set_status(
                job_id,
                status=LanguageDetectionJobStatus.DETECTING,
                progress=10,
                stage=f"Detecting language in {len(sources)} blocks",
            )
            detected = await self.detect_sources(
                sources,
                progress_callback=lambda processed, total: (
                    self._update_detection_progress(
                        job_id,
                        processed,
                        total,
                    )
                ),
                cancellation_checker=lambda: self._is_cancel_requested(job_id),
            )
            await self._set_status(
                job_id,
                status=LanguageDetectionJobStatus.AGGREGATING,
                progress=84,
                stage="Calculating preliminary language coverage",
            )
            pipeline_result = self.build_pipeline_result(
                detected,
                source_content_hash=prepared.source_content_hash,
            )
            if await self._is_cancel_requested(job_id):
                raise LanguageDetectionCancelledError
            await self._set_status(
                job_id,
                status=LanguageDetectionJobStatus.PERSISTING,
                progress=92,
                stage="Persisting language detection results",
            )
            return await self._persist(job_id, pipeline_result)
        except LanguageDetectionCancelledError:
            await self.cancel_job(job_id)
            return LanguageDetectionJobStatus.CANCELLED
        except LanguageDetectorError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.error_code,
                error_message=str(exc),
            )
            return LanguageDetectionJobStatus.FAILED
        except LanguagePipelineError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.safe_message,
                error_details=exc.details,
            )
            return LanguageDetectionJobStatus.FAILED
        except (OperationalError, ConnectionError, TimeoutError) as exc:
            raise TransientLanguageWorkerError(
                "A temporary language-detection infrastructure error occurred."
            ) from exc
        except SQLAlchemyError:
            await self.fail_job(
                job_id,
                error_code="LANGUAGE_PERSISTENCE_FAILED",
                error_message=("Language detection results could not be saved."),
            )
            return LanguageDetectionJobStatus.FAILED
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception(
                "Unexpected language detection worker error for job %s.",
                job_id,
            )
            await self.fail_job(
                job_id,
                error_code="LANGUAGE_DETECTION_FAILED",
                error_message="Language detection could not be completed.",
            )
            return LanguageDetectionJobStatus.FAILED

    async def _load_sources(
        self,
        extraction_run_id: UUID,
        ocr_run_id: UUID | None,
    ) -> list[LanguageSourceBlockData]:
        async with self.session_factory() as session:
            repository = LanguageBlockResultRepository(session)
            native = await repository.load_native_sources(
                extraction_run_id,
                limit=self.config.maximum_blocks + 1,
            )
            if len(native) > self.config.maximum_blocks:
                raise LanguagePipelineError(
                    "LANGUAGE_SOURCE_NOT_AVAILABLE",
                    "Extracted content exceeds the configured block limit.",
                    details={"maximumBlocks": self.config.maximum_blocks},
                )
            ocr: list[LanguageSourceBlockData] = []
            if ocr_run_id is not None:
                try:
                    effective_source = await OCRSourceChainService(
                        session
                    ).resolve_by_id(ocr_run_id)
                except OCRSourceChainError as exc:
                    raise LanguagePipelineError(
                        "LANGUAGE_SOURCE_NOT_AVAILABLE",
                        "The effective OCR source is not available.",
                    ) from exc
                for source_group in effective_source.pages_by_run:
                    remaining = self.config.maximum_blocks - len(native) - len(ocr)
                    source_rows = await repository.load_ocr_sources(
                        source_group.run_id,
                        extraction_run_id=extraction_run_id,
                        page_numbers=source_group.page_numbers,
                        limit=remaining + 1,
                    )
                    if len(source_rows) > remaining:
                        raise LanguagePipelineError(
                            "LANGUAGE_SOURCE_NOT_AVAILABLE",
                            ("Merged content exceeds the configured block limit."),
                            details={"maximumBlocks": (self.config.maximum_blocks)},
                        )
                    ocr.extend(source_rows)
        return self.merge_sources(native, ocr)

    def merge_sources(
        self,
        native: Sequence[LanguageSourceBlockData],
        ocr: Sequence[LanguageSourceBlockData],
    ) -> list[LanguageSourceBlockData]:
        """Prefer sufficient native PDF pages and deduplicate OCR overlap."""
        native_page_characters: dict[int, int] = defaultdict(int)
        native_page_text: dict[int, set[str]] = defaultdict(set)
        for block in native:
            if block.page_number is None:
                continue
            normalized = normalize_language_text(
                block.normalised_text or block.text
            ).casefold()
            native_page_characters[block.page_number] += len(normalized)
            if normalized:
                native_page_text[block.page_number].add(normalized)

        selected = list(native)
        ocr_seen: dict[int, set[str]] = defaultdict(set)
        for block in ocr:
            page_number = block.page_number
            if page_number is None:
                continue
            if (
                native_page_characters.get(page_number, 0)
                >= self.config.native_page_minimum_characters
            ):
                continue
            normalized = normalize_language_text(
                block.normalised_text or block.text
            ).casefold()
            if not normalized:
                selected.append(block)
                continue
            if normalized in native_page_text.get(page_number, set()):
                continue
            if normalized in ocr_seen[page_number]:
                continue
            ocr_seen[page_number].add(normalized)
            selected.append(block)
        return sorted(
            selected,
            key=lambda block: (
                block.container_index,
                block.block_order,
                (0 if block.extracted_block_id is not None else 1),
                block.source_reference,
            ),
        )

    async def detect_sources(
        self,
        sources: Sequence[LanguageSourceBlockData],
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_checker: CancellationChecker | None = None,
    ) -> list[DetectedLanguageBlockData]:
        detected: list[DetectedLanguageBlockData] = []
        total = len(sources)
        last_percent = -1
        for index, source in enumerate(sources, start=1):
            if (
                cancellation_checker is not None
                and (index == 1 or index % 25 == 0)
                and await cancellation_checker()
            ):
                raise LanguageDetectionCancelledError
            detected.append(
                DetectedLanguageBlockData(
                    source=source,
                    detection=self.detector.detect(source.text),
                )
            )
            percent = int(index * 100 / max(1, total))
            if progress_callback is not None and (
                percent != last_percent or index == total
            ):
                await progress_callback(index, total)
                last_percent = percent
        return detected

    def build_pipeline_result(
        self,
        blocks: Sequence[DetectedLanguageBlockData],
        *,
        source_content_hash: str,
    ) -> LanguagePipelineResultData:
        info = self.detector.get_detector_info()
        try:
            containers = self.aggregation.aggregate_containers(blocks)
            aggregate = self.aggregation.aggregate(blocks)
        except Exception as exc:
            raise LanguagePipelineError(
                "LANGUAGE_AGGREGATION_FAILED",
                "Language detection results could not be aggregated.",
            ) from exc
        return LanguagePipelineResultData(
            source_content_hash=source_content_hash,
            blocks=list(blocks),
            containers=containers,
            aggregate=aggregate,
            detector_name=str(info.get("name", "hybrid")),
            detector_version=str(info.get("version", "unknown")),
            warnings=[],
        )

    async def _prepare_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None,
        attempt_number: int,
    ) -> PreparedLanguageJob | LanguageDetectionJobStatus:
        async with self.session_factory() as session:
            jobs = LanguageDetectionJobRepository(session)
            job, document_file = await self._lock_job_and_source_file(
                session,
                job_id,
            )
            if job is None:
                raise LanguagePipelineError(
                    "LANGUAGE_RESULT_NOT_FOUND",
                    "The language detection job no longer exists.",
                )
            assert document_file is not None
            if job.status in {
                LanguageDetectionJobStatus.COMPLETED,
                LanguageDetectionJobStatus.PARTIALLY_COMPLETED,
                LanguageDetectionJobStatus.FAILED,
                LanguageDetectionJobStatus.CANCELLED,
            }:
                return job.status
            if job.status is LanguageDetectionJobStatus.CANCEL_REQUESTED:
                await self._mark_cancelled(session, job)
                await session.commit()
                return LanguageDetectionJobStatus.CANCELLED
            if (
                document_file.file_status is not DocumentFileStatus.AVAILABLE
                or not document_file.is_current
                or job.document.is_archived
                or document_file.document_id != job.document_id
                or document_file.document_revision_id != job.document_revision_id
            ):
                raise LanguagePipelineError(
                    "LANGUAGE_SOURCE_NOT_AVAILABLE",
                    "The source document file is no longer available.",
                )
            source_hash = await self._validate_current_source_snapshot(
                session,
                job,
                document_file,
            )
            job.source_content_hash = source_hash
            job.attempt_number = min(
                max(1, attempt_number),
                job.maximum_attempts,
            )
            job.worker_reference = worker_reference
            await jobs.update_status(
                job,
                status=LanguageDetectionJobStatus.LOADING_CONTENT,
                progress=5,
                current_stage="Loading source content",
                started_at=job.started_at or utc_now(),
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.START_LANGUAGE_DETECTION,
                entity_type="LanguageDetectionJob",
                entity_id=job.id,
                description="Language detection worker started.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "extractionRunId": str(job.extraction_run_id),
                    "ocrRunId": (
                        str(job.ocr_run_id) if job.ocr_run_id is not None else None
                    ),
                    "attemptNumber": job.attempt_number,
                },
            )
            await session.commit()
            return PreparedLanguageJob(
                extraction_run_id=job.extraction_run_id,
                ocr_run_id=job.ocr_run_id,
                source_content_hash=source_hash,
            )

    async def _persist(
        self,
        job_id: UUID,
        result: LanguagePipelineResultData,
    ) -> LanguageDetectionJobStatus:
        async with self.session_factory() as session:
            job, document_file = await self._lock_job_and_source_file(
                session,
                job_id,
            )
            if job is None:
                raise LanguagePipelineError(
                    "LANGUAGE_RESULT_NOT_FOUND",
                    "The language detection job no longer exists.",
                )
            assert document_file is not None
            if job.status is LanguageDetectionJobStatus.CANCEL_REQUESTED:
                raise LanguageDetectionCancelledError
            if job.status not in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES:
                return job.status
            await self._validate_current_source_snapshot(
                session,
                job,
                document_file,
                result_source_content_hash=result.source_content_hash,
            )
            started_at = job.started_at or utc_now()
            completed_at = utc_now()
            run = await LanguagePersistenceService(
                session,
                self.config,
            ).persist_result(
                job=job,
                result=result,
                started_at=started_at,
                completed_at=completed_at,
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.COMPLETE_LANGUAGE_DETECTION,
                entity_type="LanguageDetectionRun",
                entity_id=run.id,
                description="Language detection completed.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "runId": str(run.id),
                    "status": job.status.value,
                    "totalBlocks": result.aggregate.total_blocks,
                    "preliminary": True,
                },
            )
            await session.commit()
            return job.status

    async def _lock_job_and_source_file(
        self,
        session: AsyncSession,
        job_id: UUID,
    ) -> tuple[LanguageDetectionJob | None, DocumentFile | None]:
        """Lock file before job to match queue-side lock ordering."""
        document_file_id = await session.scalar(
            select(LanguageDetectionJob.document_file_id).where(
                LanguageDetectionJob.id == job_id
            )
        )
        if document_file_id is None:
            return None, None
        document_file = await DocumentFileRepository(session).get_by_id(
            document_file_id,
            for_update=True,
        )
        job = await LanguageDetectionJobRepository(session).get_by_id(
            job_id,
            for_update=True,
        )
        if job is None:
            return None, document_file
        if document_file is None or job.document_file_id != document_file.id:
            raise LanguagePipelineError(
                "LANGUAGE_SOURCE_NOT_AVAILABLE",
                "The source document file is no longer available.",
            )
        return job, document_file

    async def _validate_current_source_snapshot(
        self,
        session: AsyncSession,
        job: LanguageDetectionJob,
        document_file: DocumentFile,
        *,
        result_source_content_hash: str | None = None,
    ) -> str:
        """Reject work whose extraction or effective OCR pointer moved."""
        if document_file.latest_extraction_run_id != job.extraction_run_id:
            raise self._source_changed("EXTRACTION")

        extraction_run = await ExtractionRunRepository(session).get_by_id(
            job.extraction_run_id
        )
        if (
            extraction_run is None
            or extraction_run.document_file_id != job.document_file_id
        ):
            raise LanguagePipelineError(
                "LANGUAGE_SOURCE_NOT_AVAILABLE",
                "The source extraction result is not available.",
            )

        usable_ocr_statuses = {
            OCRRunStatus.COMPLETED,
            OCRRunStatus.PARTIALLY_COMPLETED,
        }
        effective_ocr_run = None
        if document_file.latest_ocr_run_id is not None:
            candidate = await OCRRunRepository(session).get_by_id(
                document_file.latest_ocr_run_id
            )
            if (
                candidate is not None
                and candidate.document_file_id == job.document_file_id
                and candidate.source_extraction_run_id == job.extraction_run_id
                and candidate.status in usable_ocr_statuses
            ):
                effective_ocr_run = candidate

        effective_ocr_run_id = (
            effective_ocr_run.id if effective_ocr_run is not None else None
        )
        if effective_ocr_run_id != job.ocr_run_id:
            raise self._source_changed("OCR")
        if extraction_run.requires_ocr and effective_ocr_run is None:
            raise LanguagePipelineError(
                "LANGUAGE_SOURCE_NOT_AVAILABLE",
                "A completed OCR result is required for this source.",
                details={"sourceType": "OCR"},
            )

        source_hash = calculate_source_snapshot_hash(
            extraction_run.content_hash,
            (effective_ocr_run.content_hash if effective_ocr_run is not None else None),
        )
        if (
            job.source_content_hash is not None
            and job.source_content_hash != source_hash
        ):
            raise self._source_changed("CONTENT")
        if (
            result_source_content_hash is not None
            and result_source_content_hash != source_hash
        ):
            raise self._source_changed("CONTENT")
        return source_hash

    @staticmethod
    def _source_changed(source_type: str) -> LanguagePipelineError:
        return LanguagePipelineError(
            "LANGUAGE_SOURCE_CHANGED",
            (
                "The source content changed while language detection was "
                "running. Queue a new job for the latest source."
            ),
            details={"sourceType": source_type},
        )

    async def _update_detection_progress(
        self,
        job_id: UUID,
        processed: int,
        total: int,
    ) -> None:
        progress = 10 + int(70 * processed / max(1, total))
        await self._set_status(
            job_id,
            status=LanguageDetectionJobStatus.DETECTING,
            progress=min(80, progress),
            stage=f"Detecting language in block {processed} of {total}",
        )

    async def _set_status(
        self,
        job_id: UUID,
        *,
        status: LanguageDetectionJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        async with self.session_factory() as session:
            repository = LanguageDetectionJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if job is None or (
                job.status is LanguageDetectionJobStatus.CANCEL_REQUESTED
            ):
                raise LanguageDetectionCancelledError
            if job.status not in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES:
                raise LanguageDetectionCancelledError
            await repository.update_status(
                job,
                status=status,
                progress=progress,
                current_stage=stage[:500],
            )
            await session.commit()

    async def _is_cancel_requested(self, job_id: UUID) -> bool:
        async with self.session_factory() as session:
            job = await LanguageDetectionJobRepository(session).get_by_id(job_id)
            return (
                job is None
                or job.status is LanguageDetectionJobStatus.CANCEL_REQUESTED
                or job.status is LanguageDetectionJobStatus.CANCELLED
            )

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
                repository = LanguageDetectionJobRepository(session)
                job = await repository.get_by_id(
                    job_id,
                    for_update=True,
                )
                if (
                    job is None
                    or job.status not in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES
                ):
                    return
                if job.status is LanguageDetectionJobStatus.CANCEL_REQUESTED:
                    await self._mark_cancelled(session, job)
                else:
                    await repository.mark_failed(
                        job,
                        failed_at=utc_now(),
                        error_code=error_code,
                        error_message=error_message,
                        error_details=error_details,
                    )
                    await AuditLogRepository(session).create(
                        user_id=job.requested_by,
                        action=AuditAction.FAIL_LANGUAGE_DETECTION,
                        entity_type="LanguageDetectionJob",
                        entity_id=job.id,
                        description="Language detection failed.",
                        new_values={
                            "documentFileId": str(job.document_file_id),
                            "errorCode": error_code,
                        },
                    )
                await session.commit()
        except SQLAlchemyError:
            return

    async def cancel_job(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            repository = LanguageDetectionJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if job is None or job.status not in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES:
                return
            await self._mark_cancelled(session, job)
            await session.commit()

    @staticmethod
    async def _mark_cancelled(
        session: AsyncSession,
        job: LanguageDetectionJob,
    ) -> None:
        await LanguageDetectionJobRepository(session).mark_cancelled(
            job,
            cancelled_at=utc_now(),
        )
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.CANCEL_LANGUAGE_DETECTION,
            entity_type="LanguageDetectionJob",
            entity_id=job.id,
            description="Language detection cancelled.",
            new_values={
                "documentFileId": str(job.document_file_id),
                "status": LanguageDetectionJobStatus.CANCELLED.value,
            },
        )

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
                        "Failed to release language lock for %s.",
                        job_id,
                    )
