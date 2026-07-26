"""Worker-side extraction orchestration with brief database transactions."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import BinaryIO, cast
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
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extraction_job import (
    ACTIVE_EXTRACTION_JOB_STATUSES,
    ExtractionJob,
    ExtractionJobStatus,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_job_repository import ExtractionJobRepository
from app.services.extraction.base_extractor import (
    ExtractionCancelledError,
    ExtractionError,
)
from app.services.extraction.extraction_cleanup_service import (
    ExtractionCleanupService,
)
from app.services.extraction.extraction_persistence_service import (
    ExtractionPersistenceService,
)
from app.services.extraction.extractor_factory import get_extractor
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_factory import get_storage
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class TransientExtractionWorkerError(Exception):
    """Safe marker for infrastructure failures eligible for Celery retry."""


class ExtractionService:
    """Run one extraction without retaining a database connection while parsing."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        storage: BaseStorage | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or AsyncSessionFactory
        self.storage = storage or get_storage(self.settings)

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None = None,
        attempt_number: int = 1,
    ) -> ExtractionJobStatus:
        """Serialize duplicate deliveries with a database advisory lock."""
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
    ) -> ExtractionJobStatus:
        """Inspect, extract, and atomically persist one queued job."""
        local_path: Path | None = None
        temporary_directory: Path | None = None
        try:
            prepared = await self._prepare_job(
                job_id,
                worker_reference=worker_reference,
                attempt_number=attempt_number,
            )
            if isinstance(prepared, ExtractionJobStatus):
                return prepared
            source = prepared
            temporary_directory = Path(
                tempfile.mkdtemp(prefix="document-extraction-")
            )
            local_path = temporary_directory / (
                f"source.{source.file_extension}"
            )
            await self._copy_source(source, local_path)
            extractor = get_extractor(source.file_extension)
            await self._set_status(
                job_id,
                status=ExtractionJobStatus.INSPECTING,
                progress=5,
                stage=f"Inspecting {source.file_extension.upper()}",
            )
            await extractor.inspect(local_path)
            if await self._is_cancel_requested(job_id):
                raise ExtractionCancelledError

            await self._set_status(
                job_id,
                status=ExtractionJobStatus.EXTRACTING,
                progress=10,
                stage=f"Extracting {source.file_extension.upper()} content",
            )
            result = await extractor.extract(
                local_path,
                {
                    "settings": self.settings,
                    "progress_callback": (
                        lambda progress, stage: self._update_progress(
                            job_id,
                            progress,
                            stage,
                        )
                    ),
                    "cancellation_checker": (
                        lambda: self._is_cancel_requested(job_id)
                    ),
                },
            )
            await self._set_status(
                job_id,
                status=ExtractionJobStatus.NORMALISING,
                progress=80,
                stage="Normalising extracted content",
            )
            if await self._is_cancel_requested(job_id):
                raise ExtractionCancelledError

            await self._set_status(
                job_id,
                status=ExtractionJobStatus.PERSISTING,
                progress=90,
                stage="Persisting extracted content",
            )
            return await self._persist(job_id, result)
        except ExtractionCancelledError:
            await self.cancel_job(job_id)
            return ExtractionJobStatus.CANCELLED
        except ExtractionError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.safe_message,
                error_details=cast(dict[str, object], exc.details),
            )
            return ExtractionJobStatus.FAILED
        except (OperationalError, ConnectionError, TimeoutError) as exc:
            raise TransientExtractionWorkerError(
                "A temporary extraction infrastructure error occurred."
            ) from exc
        except SQLAlchemyError:
            await self.fail_job(
                job_id,
                error_code="EXTRACTION_PERSISTENCE_FAILED",
                error_message=(
                    "The extracted content could not be saved."
                ),
            )
            return ExtractionJobStatus.FAILED
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception(
                "Unexpected extraction worker error for job %s.",
                job_id,
            )
            await self.fail_job(
                job_id,
                error_code="EXTRACTION_WORKER_FAILED",
                error_message="The extraction worker could not process the file.",
            )
            return ExtractionJobStatus.FAILED
        finally:
            if local_path is not None:
                await ExtractionCleanupService.remove_file(local_path)
            if temporary_directory is not None:
                await asyncio.to_thread(
                    _remove_empty_temporary_directory,
                    temporary_directory,
                )

    @asynccontextmanager
    async def _execution_lock(
        self,
        job_id: UUID,
    ) -> AsyncIterator[None]:
        """Prevent concurrent at-least-once deliveries for one job.

        PostgreSQL session-level advisory locks automatically release if a
        worker process or its connection dies. SQLite tests remain serialized
        by their caller and do not emulate this PostgreSQL facility.
        """
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
                    # Closing the dedicated connection also releases the lock.
                    logger.exception(
                        "Failed to explicitly release extraction lock for %s.",
                        job_id,
                    )

    async def fail_job(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        error_details: dict[str, object] | None = None,
    ) -> None:
        """Mark one non-terminal job failed with client-safe diagnostics."""
        try:
            async with self.session_factory() as session:
                repository = ExtractionJobRepository(session)
                job = await repository.get_by_id(job_id, for_update=True)
                if job is None or job.status not in ACTIVE_EXTRACTION_JOB_STATUSES:
                    return
                if job.status is ExtractionJobStatus.CANCEL_REQUESTED:
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
                        action=AuditAction.FAIL_DOCUMENT_EXTRACTION,
                        entity_type="ExtractionJob",
                        entity_id=job.id,
                        description="Document extraction failed.",
                        new_values={
                            "documentFileId": str(job.document_file_id),
                            "errorCode": error_code,
                        },
                    )
                await session.commit()
        except SQLAlchemyError:
            # A failed database connection cannot reliably persist its own
            # failure. Celery logs retain the task-level infrastructure event.
            return

    async def cancel_job(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            repository = ExtractionJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if job is None or job.status not in ACTIVE_EXTRACTION_JOB_STATUSES:
                return
            await self._mark_cancelled(session, job)
            await session.commit()

    async def _prepare_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str | None,
        attempt_number: int,
    ) -> DocumentFile | ExtractionJobStatus:
        async with self.session_factory() as session:
            jobs = ExtractionJobRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            if job is None:
                raise ExtractionError(
                    "EXTRACTION_WORKER_FAILED",
                    "The extraction job no longer exists.",
                )
            if job.status in {
                ExtractionJobStatus.COMPLETED,
                ExtractionJobStatus.PARTIALLY_COMPLETED,
                ExtractionJobStatus.OCR_REQUIRED,
                ExtractionJobStatus.FAILED,
                ExtractionJobStatus.CANCELLED,
            }:
                return job.status
            if job.status is ExtractionJobStatus.CANCEL_REQUESTED:
                await self._mark_cancelled(session, job)
                await session.commit()
                return ExtractionJobStatus.CANCELLED

            document_file = job.document_file
            if (
                document_file.file_status is not DocumentFileStatus.AVAILABLE
                or not document_file.is_current
                or document_file.document_id != job.document_id
                or document_file.document_revision_id
                != job.document_revision_id
                or job.document.is_archived
            ):
                raise ExtractionError(
                    "FILE_NOT_AVAILABLE",
                    "The source document file is no longer available.",
                )
            if (
                document_file.file_size
                > self.settings.extraction_max_file_size_mb * 1024 * 1024
            ):
                raise ExtractionError(
                    "EXTRACTION_FILE_TOO_LARGE",
                    "The document exceeds the configured extraction limit.",
                )

            job.attempt_number = min(
                max(1, attempt_number),
                job.maximum_attempts,
            )
            job.worker_reference = worker_reference
            await jobs.update_status(
                job,
                status=ExtractionJobStatus.INSPECTING,
                progress=5,
                current_stage=(
                    f"Inspecting {document_file.file_extension.upper()}"
                ),
                started_at=job.started_at or utc_now(),
            )
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=AuditAction.START_DOCUMENT_EXTRACTION,
                entity_type="ExtractionJob",
                entity_id=job.id,
                description="Document extraction worker started.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "attemptNumber": job.attempt_number,
                },
            )
            await session.commit()
            return document_file

    async def _copy_source(
        self,
        document_file: DocumentFile,
        destination: Path,
    ) -> None:
        try:
            source = await self.storage.open(document_file.storage_key)
        except FileNotFoundError as exc:
            raise ExtractionError(
                "FILE_NOT_FOUND_IN_STORAGE",
                "The source document file could not be found in storage.",
            ) from exc
        try:
            actual_size, actual_hash = await asyncio.to_thread(
                _copy_and_hash,
                source,
                destination,
                self.settings.extraction_max_file_size_mb * 1024 * 1024,
            )
        finally:
            await asyncio.to_thread(source.close)

        if (
            actual_size != document_file.file_size
            or actual_hash != document_file.sha256_hash
        ):
            await ExtractionCleanupService.remove_file(destination)
            raise ExtractionError(
                "FILE_NOT_AVAILABLE",
                "The source file failed its extraction integrity check.",
            )

    async def _update_progress(
        self,
        job_id: UUID,
        progress: int,
        stage: str,
    ) -> None:
        async with self.session_factory() as session:
            repository = ExtractionJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if job is None or job.status is ExtractionJobStatus.CANCEL_REQUESTED:
                raise ExtractionCancelledError
            if job.status not in ACTIVE_EXTRACTION_JOB_STATUSES:
                raise ExtractionCancelledError
            await repository.update_status(
                job,
                status=ExtractionJobStatus.EXTRACTING,
                progress=min(75, max(10, progress)),
                current_stage=stage[:500],
            )
            await session.commit()

    async def _set_status(
        self,
        job_id: UUID,
        *,
        status: ExtractionJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        async with self.session_factory() as session:
            repository = ExtractionJobRepository(session)
            job = await repository.get_by_id(job_id, for_update=True)
            if job is None or job.status is ExtractionJobStatus.CANCEL_REQUESTED:
                raise ExtractionCancelledError
            if job.status not in ACTIVE_EXTRACTION_JOB_STATUSES:
                raise ExtractionCancelledError
            await repository.update_status(
                job,
                status=status,
                progress=progress,
                current_stage=stage,
            )
            await session.commit()

    async def _is_cancel_requested(self, job_id: UUID) -> bool:
        async with self.session_factory() as session:
            job = await ExtractionJobRepository(session).get_by_id(job_id)
            return (
                job is None
                or job.status is ExtractionJobStatus.CANCEL_REQUESTED
                or job.status is ExtractionJobStatus.CANCELLED
            )

    async def _persist(
        self,
        job_id: UUID,
        result: object,
    ) -> ExtractionJobStatus:
        from app.schemas.extraction import ExtractedDocumentData

        if not isinstance(result, ExtractedDocumentData):
            raise ExtractionError(
                "EXTRACTION_WORKER_FAILED",
                "The extractor returned an invalid result.",
            )
        async with self.session_factory() as session:
            jobs = ExtractionJobRepository(session)
            files = DocumentFileRepository(session)
            job = await jobs.get_by_id(job_id, for_update=True)
            if job is None:
                raise ExtractionError(
                    "EXTRACTION_WORKER_FAILED",
                    "The extraction job no longer exists.",
                )
            if job.status is ExtractionJobStatus.CANCEL_REQUESTED:
                raise ExtractionCancelledError
            document_file = await files.get_by_id(
                job.document_file_id,
                for_update=True,
            )
            if (
                document_file is None
                or document_file.file_status
                is not DocumentFileStatus.AVAILABLE
                or not document_file.is_current
                or document_file.sha256_hash
                != job.document_file.sha256_hash
            ):
                raise ExtractionError(
                    "FILE_NOT_AVAILABLE",
                    "The source document file is no longer available.",
                )
            run = await ExtractionPersistenceService(
                session,
                settings=self.settings,
            ).persist_result(
                job=job,
                document_file=document_file,
                result=result,
                completed_at=utc_now(),
            )
            action = {
                ExtractionJobStatus.COMPLETED: (
                    AuditAction.COMPLETE_DOCUMENT_EXTRACTION
                ),
                ExtractionJobStatus.PARTIALLY_COMPLETED: (
                    AuditAction.PARTIAL_DOCUMENT_EXTRACTION
                ),
                ExtractionJobStatus.OCR_REQUIRED: (
                    AuditAction.DOCUMENT_REQUIRES_OCR
                ),
            }[job.status]
            await AuditLogRepository(session).create(
                user_id=job.requested_by,
                action=action,
                entity_type="ExtractionRun",
                entity_id=run.id,
                description=(
                    "Document extraction completed."
                    if job.status is ExtractionJobStatus.COMPLETED
                    else (
                        "Document extraction completed with warnings."
                        if job.status
                        is ExtractionJobStatus.PARTIALLY_COMPLETED
                        else "Document inspection requires OCR."
                    )
                ),
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "status": job.status.value,
                    "runId": str(run.id),
                },
            )
            await session.commit()
            return job.status

    @staticmethod
    async def _mark_cancelled(
        session: AsyncSession,
        job: ExtractionJob,
    ) -> None:
        await ExtractionJobRepository(session).mark_cancelled(
            job,
            cancelled_at=utc_now(),
        )
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.CANCEL_DOCUMENT_EXTRACTION,
            entity_type="ExtractionJob",
            entity_id=job.id,
            description="Document extraction cancelled.",
            new_values={
                "documentFileId": str(job.document_file_id),
                "status": ExtractionJobStatus.CANCELLED.value,
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
                    raise ExtractionError(
                        "EXTRACTION_FILE_TOO_LARGE",
                        "The document exceeds the configured extraction limit.",
                    )
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return total, digest.hexdigest()


def _remove_empty_temporary_directory(path: Path) -> None:
    """Remove only the exact worker-created directory after its file is gone."""
    try:
        path.rmdir()
    except OSError:
        return
