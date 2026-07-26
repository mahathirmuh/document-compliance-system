"""Database orchestration for the dedicated local similarity worker."""

from __future__ import annotations

import logging
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.models.document_file import DocumentFileStatus
from app.models.similarity_enums import (
    TERMINAL_SIMILARITY_JOB_STATUSES,
    SimilarityJobStatus,
)
from app.models.similarity_job import SimilarityJob
from app.repositories.audit_log import AuditLogRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.similarity_job_repository import (
    SimilarityJobRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.services.similarity.alignment.long_text_chunking_service import (
    LongTextChunkingService,
)
from app.services.similarity.base_similarity_provider import (
    SimilarityProviderError,
    SimilarityProviderUnavailable,
)
from app.services.similarity.similarity_context_service import (
    SimilarityContextError,
    SimilarityContextService,
)
from app.services.similarity.similarity_persistence_service import (
    SimilarityPersistenceService,
)
from app.services.similarity.similarity_provider_factory import (
    SimilarityProviderFactory,
)
from app.services.similarity.translation_similarity_service import (
    SimilarityAnalysisCancelled,
    TranslationSimilarityService,
)
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class SimilarityWorkerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TransientSimilarityWorkerError(RuntimeError):
    """Infrastructure failure eligible for a bounded Celery retry."""


class SimilarityWorkerService:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
        provider=None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.provider = provider or SimilarityProviderFactory.create(settings)
        self.contexts = SimilarityContextService(settings)
        self.pipeline = TranslationSimilarityService(
            provider=self.provider,
            chunking=LongTextChunkingService(
                text_max_characters=int(
                    getattr(
                        settings,
                        "similarity_text_max_characters",
                        12000,
                    )
                ),
                chunk_max_characters=int(
                    getattr(
                        settings,
                        "similarity_chunk_max_characters",
                        1500,
                    )
                ),
                overlap_characters=int(
                    getattr(
                        settings,
                        "similarity_chunk_overlap_characters",
                        150,
                    )
                ),
                maximum_chunks=int(
                    getattr(
                        settings,
                        "similarity_max_chunks_per_text",
                        50,
                    )
                ),
            ),
        )

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> SimilarityJobStatus:
        try:
            async with self.session_factory() as session:
                job, acquired = await self._start_job(
                    session,
                    job_id,
                    worker_reference=worker_reference,
                    attempt_number=attempt_number,
                )
                if job is None:
                    return SimilarityJobStatus.FAILED
                if job.status in TERMINAL_SIMILARITY_JOB_STATUSES:
                    return job.status
                if job.status is SimilarityJobStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, job)
                if not acquired:
                    return job.status
                context = await self.contexts.build(
                    session,
                    document_file_id=job.document_file_id,
                    compliance_run_id=job.compliance_run_id,
                    language_detection_run_id=(
                        job.language_detection_run_id
                    ),
                )
                await self._set_progress(
                    session,
                    job,
                    status=SimilarityJobStatus.LOADING_MODEL,
                    progress=10,
                    stage="Checking local similarity model",
                )
                if not self.provider.is_ready():
                    raise SimilarityProviderUnavailable(
                        "The configured local similarity model is unavailable."
                    )

                async def cancellation_requested() -> bool:
                    status = await session.scalar(
                        select(SimilarityJob.status)
                        .where(SimilarityJob.id == job.id)
                        .execution_options(populate_existing=True)
                    )
                    return status is SimilarityJobStatus.CANCEL_REQUESTED

                last_progress: tuple[str, int] | None = None

                async def update_progress(stage: str, progress: int) -> None:
                    nonlocal last_progress
                    current = (stage, progress)
                    if current == last_progress:
                        return
                    last_progress = current
                    await self._set_progress(
                        session,
                        job,
                        status=SimilarityJobStatus(stage),
                        progress=progress,
                        stage=stage.replace("_", " ").title(),
                    )

                result = await self.pipeline.analyse(
                    context,
                    cancellation_check=cancellation_requested,
                    progress_callback=update_progress,
                )
                if await cancellation_requested():
                    raise SimilarityAnalysisCancelled()
                await self._set_progress(
                    session,
                    job,
                    status=SimilarityJobStatus.PERSISTING,
                    progress=97,
                    stage="Persisting official similarity result",
                )
                locked = await SimilarityJobRepository(session).get_by_id(
                    job.id, for_update=True
                )
                if locked is None:
                    raise SimilarityWorkerError(
                        "SIMILARITY_JOB_NOT_FOUND",
                        "The similarity job no longer exists.",
                    )
                if locked.status in TERMINAL_SIMILARITY_JOB_STATUSES:
                    return locked.status
                if locked.status is SimilarityJobStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, locked)
                details = dict(locked.error_details_json or {})
                if (
                    details.get("workerReference") != worker_reference
                    or details.get("workerAttempt") != attempt_number
                ):
                    return locked.status
                fresh_file = await DocumentFileRepository(session).get_by_id(
                    locked.document_file_id, for_update=True
                )
                if (
                    fresh_file is None
                    or not fresh_file.is_current
                    or fresh_file.file_status
                    is not DocumentFileStatus.AVAILABLE
                    or fresh_file.deleted_at is not None
                    or fresh_file.document.is_archived
                    or fresh_file.latest_compliance_run_id
                    != locked.compliance_run_id
                    or fresh_file.latest_language_detection_run_id
                    != locked.language_detection_run_id
                    or locked.source_content_hash
                    != context.source_content_hash
                ):
                    raise SimilarityWorkerError(
                        "SIMILARITY_SOURCE_CHANGED",
                        (
                            "The retained source changed before the "
                            "similarity result could be persisted."
                        ),
                    )
                existing = await SimilarityRunRepository(
                    session
                ).get_by_job_id(locked.id)
                if existing is not None:
                    return locked.status
                run = await SimilarityPersistenceService(
                    session, self.settings
                ).persist(locked, result)
                await AuditLogRepository(session).create(
                    user_id=locked.requested_by,
                    action=AuditAction.COMPLETE_TRANSLATION_SIMILARITY,
                    entity_type="SimilarityRun",
                    entity_id=run.id,
                    description="Translation similarity analysis completed.",
                    new_values={
                        "jobId": str(locked.id),
                        "documentFileId": str(locked.document_file_id),
                        "status": run.status.value,
                        "averageSimilarity": (
                            float(run.average_similarity)
                            if run.average_similarity is not None
                            else None
                        ),
                        "sourceContentHash": run.source_content_hash,
                    },
                )
                await session.commit()
                return locked.status
        except SimilarityAnalysisCancelled:
            async with self.session_factory() as session:
                job = await SimilarityJobRepository(session).get_by_id(
                    job_id, for_update=True
                )
                if job is None:
                    return SimilarityJobStatus.CANCELLED
                return await self._cancel(session, job)
        except SimilarityProviderUnavailable:
            await self.fail_job(
                job_id,
                error_code="SIMILARITY_MODEL_UNAVAILABLE",
                error_message=(
                    "The configured local similarity model is unavailable."
                ),
            )
            return SimilarityJobStatus.FAILED
        except SimilarityContextError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message="The similarity context could not be prepared.",
            )
            return SimilarityJobStatus.FAILED
        except SimilarityWorkerError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=str(exc),
            )
            return SimilarityJobStatus.FAILED
        except SimilarityProviderError:
            await self.fail_job(
                job_id,
                error_code="SIMILARITY_INFERENCE_FAILED",
                error_message="The local similarity model could not analyse the text.",
            )
            return SimilarityJobStatus.FAILED
        except (DBAPIError, OSError) as exc:
            logger.warning(
                "Transient similarity worker failure for %s: %s",
                job_id,
                type(exc).__name__,
            )
            raise TransientSimilarityWorkerError(
                "The similarity data source is temporarily unavailable."
            ) from exc
        except SoftTimeLimitExceeded:
            raise
        except SQLAlchemyError:
            await self.fail_job(
                job_id,
                error_code="SIMILARITY_PERSISTENCE_FAILED",
                error_message="The similarity result could not be persisted.",
            )
            logger.exception("Similarity persistence failed for %s.", job_id)
            return SimilarityJobStatus.FAILED
        except (TypeError, ValueError):
            await self.fail_job(
                job_id,
                error_code="SIMILARITY_ANALYSIS_FAILED",
                error_message="Similarity analysis could not be completed.",
            )
            logger.exception("Similarity analysis failed for %s.", job_id)
            return SimilarityJobStatus.FAILED
        except Exception:
            await self.fail_job(
                job_id,
                error_code="SIMILARITY_ANALYSIS_FAILED",
                error_message="Similarity analysis could not be completed.",
            )
            logger.exception(
                "Unexpected similarity worker failure for %s.", job_id
            )
            return SimilarityJobStatus.FAILED

    async def _start_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> tuple[SimilarityJob | None, bool]:
        job = await SimilarityJobRepository(session).get_by_id(
            job_id, for_update=True
        )
        if job is None or job.status in TERMINAL_SIMILARITY_JOB_STATUSES:
            return job, False
        if job.status is SimilarityJobStatus.CANCEL_REQUESTED:
            return job, False
        details = dict(job.error_details_json or {})
        same_retry = (
            details.get("workerReference") == worker_reference
            and attempt_number > job.attempt_number
        )
        if job.status is not SimilarityJobStatus.QUEUED and not same_retry:
            return job, False
        job.status = SimilarityJobStatus.LOADING_CONTEXT
        job.progress = max(job.progress, 5)
        job.current_stage = "Loading retained similarity context"
        job.started_at = job.started_at or utc_now()
        job.attempt_number = min(
            max(1, attempt_number), job.maximum_attempts
        )
        details["workerReference"] = worker_reference
        details["workerAttempt"] = attempt_number
        job.error_details_json = details
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.START_TRANSLATION_SIMILARITY,
            entity_type="SimilarityJob",
            entity_id=job.id,
            description="Translation similarity analysis started.",
            new_values={
                "documentFileId": str(job.document_file_id),
                "attemptNumber": job.attempt_number,
            },
        )
        await session.commit()
        return job, True

    async def _set_progress(
        self,
        session: AsyncSession,
        job: SimilarityJob,
        *,
        status: SimilarityJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        result = await session.execute(
            update(SimilarityJob)
            .where(
                SimilarityJob.id == job.id,
                SimilarityJob.status
                != SimilarityJobStatus.CANCEL_REQUESTED,
                SimilarityJob.status.not_in(
                    list(TERMINAL_SIMILARITY_JOB_STATUSES)
                ),
            )
            .values(
                status=status,
                progress=max(0, min(100, progress)),
                current_stage=stage[:500],
            )
        )
        await session.commit()
        await session.refresh(job)
        if result.rowcount != 1:
            if job.status is SimilarityJobStatus.CANCEL_REQUESTED:
                raise SimilarityAnalysisCancelled()
            raise SimilarityWorkerError(
                "SIMILARITY_JOB_NOT_ACTIVE",
                "The similarity job is no longer active.",
            )

    async def _cancel(
        self,
        session: AsyncSession,
        job: SimilarityJob,
    ) -> SimilarityJobStatus:
        job.status = SimilarityJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = utc_now()
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.CANCEL_TRANSLATION_SIMILARITY,
            entity_type="SimilarityJob",
            entity_id=job.id,
            description="Translation similarity analysis cancelled.",
            new_values={"documentFileId": str(job.document_file_id)},
        )
        await session.commit()
        return job.status

    async def fail_job(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        try:
            async with self.session_factory() as session:
                job = await SimilarityJobRepository(session).get_by_id(
                    job_id, for_update=True
                )
                if (
                    job is None
                    or job.status in TERMINAL_SIMILARITY_JOB_STATUSES
                ):
                    return
                job.status = SimilarityJobStatus.FAILED
                job.current_stage = "Failed"
                job.failed_at = utc_now()
                job.error_code = error_code[:100]
                job.error_message = error_message[:2000]
                await AuditLogRepository(session).create(
                    user_id=job.requested_by,
                    action=AuditAction.FAIL_TRANSLATION_SIMILARITY,
                    entity_type="SimilarityJob",
                    entity_id=job.id,
                    description="Translation similarity analysis failed.",
                    new_values={
                        "documentFileId": str(job.document_file_id),
                        "errorCode": job.error_code,
                    },
                )
                await session.commit()
        except SQLAlchemyError:
            logger.exception(
                "Could not persist similarity failure for %s.", job_id
            )
