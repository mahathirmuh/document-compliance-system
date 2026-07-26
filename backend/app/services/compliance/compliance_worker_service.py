"""Database orchestration for the dedicated Phase 8 compliance worker."""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update
from sqlalchemy import text as sql_text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.models.compliance_enums import (
    TERMINAL_COMPLIANCE_JOB_STATUSES,
    ComplianceJobStatus,
)
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.document_file import DocumentFileStatus
from app.models.extraction_run import ExtractionRunStatus
from app.models.language_detection_run import LanguageDetectionRunStatus
from app.models.ocr_run import OCRRunStatus
from app.models.validation_finding import ValidationFinding
from app.repositories.audit_log import AuditLogRepository
from app.repositories.compliance_job_repository import (
    ComplianceJobRepository,
)
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extracted_table_repository import (
    ExtractedTableRepository,
)
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.repositories.section_alias_profile_repository import (
    SectionAliasProfileRepository,
)
from app.repositories.section_alias_repository import SectionAliasRepository
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.compliance_internal import SectionAliasData
from app.services.compliance.compliance_context_service import (
    ComplianceContextBuildError,
    ComplianceContextService,
)
from app.services.compliance.compliance_persistence_service import (
    CompliancePersistenceService,
)
from app.services.compliance.compliance_pipeline import (
    COMPLIANCE_VALIDATION_FAILED,
    CompliancePipeline,
    CompliancePipelineCancelled,
    CompliancePipelineStageError,
)
from app.services.compliance.grouping.paragraph_grouping_service import (
    ParagraphGroupingService,
)
from app.services.compliance.grouping.positional_grouping_service import (
    PositionalGroupingService,
)
from app.services.compliance.grouping.translation_group_service import (
    TranslationGroupService,
)
from app.services.compliance.sections.heading_candidate_service import (
    HeadingCandidateService,
)
from app.services.compliance.sections.section_detector import SectionDetector
from app.services.compliance.sections.section_matcher import SectionMatcher
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)

_LOCAL_LEASE_GUARD = threading.Lock()
_LOCAL_LEASES: set[UUID] = set()

_USABLE_EXTRACTION_STATUSES = {
    ExtractionRunStatus.COMPLETED,
    ExtractionRunStatus.PARTIALLY_COMPLETED,
    ExtractionRunStatus.OCR_REQUIRED,
}
_USABLE_OCR_STATUSES = {
    OCRRunStatus.COMPLETED,
    OCRRunStatus.PARTIALLY_COMPLETED,
}
_USABLE_LANGUAGE_STATUSES = {
    LanguageDetectionRunStatus.COMPLETED,
    LanguageDetectionRunStatus.PARTIALLY_COMPLETED,
}


class ComplianceWorkerError(RuntimeError):
    """Controlled non-retryable worker failure with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TransientComplianceWorkerError(RuntimeError):
    """Infrastructure failure that may be retried by Celery."""


class ComplianceWorkerService:
    """Load retained evidence, run pure validation, and persist atomically."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.contexts = ComplianceContextService(
            maximum_blocks=settings.compliance_max_blocks,
        )
        self.pipeline = CompliancePipeline(
            context_service=self.contexts,
            section_detector=SectionDetector(
                candidate_service=HeadingCandidateService(
                    maximum_characters=(settings.section_heading_max_characters),
                ),
                matcher=SectionMatcher(
                    minimum_confidence=(settings.section_match_min_confidence),
                    fuzzy_threshold=(settings.section_fuzzy_match_threshold),
                    regex_max_length=(settings.section_alias_regex_max_length),
                    regex_timeout_ms=(settings.section_alias_regex_timeout_ms),
                ),
            ),
            grouping_service=TranslationGroupService(
                paragraph_service=ParagraphGroupingService(
                    maximum_block_distance=(
                        settings.translation_group_max_block_distance
                    ),
                ),
                positional_service=PositionalGroupingService(
                    maximum_vertical_gap=(settings.translation_group_max_vertical_gap),
                    maximum_block_distance=(
                        settings.translation_group_max_block_distance
                    ),
                ),
                maximum_groups=(settings.compliance_max_translation_groups),
            ),
        )

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> ComplianceJobStatus:
        """Process one job under a cross-worker, crash-safe execution lease."""

        try:
            async with self._execution_lease(job_id) as acquired:
                if not acquired:
                    async with self.session_factory() as session:
                        job = await ComplianceJobRepository(session).get_by_id(job_id)
                        return (
                            job.status
                            if job is not None
                            else ComplianceJobStatus.FAILED
                        )
                return await self._process_job(
                    job_id,
                    worker_reference=worker_reference,
                    attempt_number=attempt_number,
                )
        except TransientComplianceWorkerError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            logger.warning(
                "Transient compliance lease failure for job %s: %s",
                job_id,
                type(exc).__name__,
            )
            raise TransientComplianceWorkerError(
                "The compliance worker lease is temporarily unavailable."
            ) from exc

    async def _process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> ComplianceJobStatus:
        """Process one durable job; repeated delivery remains idempotent."""

        try:
            async with self.session_factory() as session:
                job, lease_acquired = await self._start_job(
                    session,
                    job_id,
                    worker_reference=worker_reference,
                    attempt_number=attempt_number,
                    allow_redelivery=True,
                )
                if job is None:
                    return ComplianceJobStatus.FAILED
                if job.status in TERMINAL_COMPLIANCE_JOB_STATUSES:
                    return job.status
                if job.status is ComplianceJobStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, job)
                if not lease_acquired:
                    return job.status

                context, previous_findings = await self._load_context(
                    session,
                    job,
                )
                await self._set_progress(
                    session,
                    job,
                    status=ComplianceJobStatus.DETECTING_SECTIONS,
                    progress=15,
                    stage="Detecting canonical sections",
                )
                active_job = job
                current_job_id = active_job.id

                async def cancellation_requested() -> bool:
                    status = await session.scalar(
                        select(ComplianceJob.status)
                        .where(ComplianceJob.id == current_job_id)
                        .execution_options(populate_existing=True)
                    )
                    return status is ComplianceJobStatus.CANCEL_REQUESTED

                async def update_progress(stage: str, progress: int) -> None:
                    status = ComplianceJobStatus(stage)
                    await self._set_progress(
                        session,
                        active_job,
                        status=status,
                        progress=progress,
                        stage=stage.replace("_", " ").title(),
                    )

                result = await self.pipeline.run(
                    context,
                    cancellation_check=cancellation_requested,
                    progress_callback=update_progress,
                    previous_findings=previous_findings,
                )
                if await cancellation_requested():
                    raise CompliancePipelineCancelled(
                        "Compliance validation was cancelled."
                    )
                await self._set_progress(
                    session,
                    job,
                    status=ComplianceJobStatus.PERSISTING,
                    progress=97,
                    stage="Persisting official compliance result",
                )
                # Refresh under lock after the progress commit. The run and all
                # children below are committed together.
                locked = await ComplianceJobRepository(session).get_by_id(
                    job.id,
                    for_update=True,
                )
                if locked is None:
                    raise ComplianceWorkerError(
                        "COMPLIANCE_JOB_NOT_FOUND",
                        "The compliance job no longer exists.",
                    )
                if locked.status in TERMINAL_COMPLIANCE_JOB_STATUSES:
                    return locked.status
                if locked.status is ComplianceJobStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, locked)
                locked_details = dict(locked.error_details_json or {})
                if (
                    locked_details.get("workerReference") != worker_reference
                    or locked_details.get("workerAttempt") != attempt_number
                ):
                    return locked.status
                fresh_file = await DocumentFileRepository(session).get_by_id(
                    locked.document_file_id,
                    for_update=True,
                )
                if (
                    fresh_file is None
                    or not fresh_file.is_current
                    or fresh_file.file_status is not DocumentFileStatus.AVAILABLE
                    or fresh_file.deleted_at is not None
                    or fresh_file.document.is_archived
                    or fresh_file.latest_extraction_run_id != locked.extraction_run_id
                    or fresh_file.latest_ocr_run_id != locked.ocr_run_id
                    or fresh_file.latest_language_detection_run_id
                    != locked.language_detection_run_id
                ):
                    raise ComplianceWorkerError(
                        "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                        (
                            "The source changed before the compliance result "
                            "could be persisted."
                        ),
                    )
                run = await CompliancePersistenceService(
                    session,
                    self.settings,
                ).persist(locked, result)
                await AuditLogRepository(session).create(
                    user_id=locked.requested_by,
                    action=(
                        AuditAction.PARTIAL_COMPLIANCE_VALIDATION
                        if run.status.value == "PARTIALLY_COMPLETED"
                        else AuditAction.COMPLETE_COMPLIANCE_VALIDATION
                    ),
                    entity_type="ComplianceRun",
                    entity_id=run.id,
                    description="Compliance validation completed.",
                    new_values={
                        "jobId": str(locked.id),
                        "documentFileId": str(locked.document_file_id),
                        "complianceStatus": run.compliance_status.value,
                        "complianceScore": float(run.compliance_score),
                        "sourceContentHash": run.source_content_hash,
                    },
                )
                await session.commit()
                return locked.status
        except CompliancePipelineCancelled:
            async with self.session_factory() as session:
                job = await ComplianceJobRepository(session).get_by_id(
                    job_id,
                    for_update=True,
                )
                if job is None:
                    return ComplianceJobStatus.CANCELLED
                return await self._cancel(session, job)
        except CompliancePipelineStageError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.public_message,
            )
            logger.warning(
                "Compliance pipeline stage %s failed for job %s.",
                exc.code,
                job_id,
            )
            return ComplianceJobStatus.FAILED
        except ComplianceContextBuildError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=("Compliance validation context could not be prepared."),
            )
            logger.warning(
                "Compliance context build failed for job %s.",
                job_id,
            )
            return ComplianceJobStatus.FAILED
        except ComplianceWorkerError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=str(exc),
            )
            return ComplianceJobStatus.FAILED
        except (DBAPIError, OSError) as exc:
            logger.warning(
                "Transient compliance worker failure for job %s: %s",
                job_id,
                type(exc).__name__,
            )
            raise TransientComplianceWorkerError(
                "The compliance data source is temporarily unavailable."
            ) from exc
        except SQLAlchemyError:
            await self.fail_job(
                job_id,
                error_code="COMPLIANCE_PERSISTENCE_FAILED",
                error_message="The compliance result could not be persisted.",
            )
            logger.exception("Compliance persistence failed for %s.", job_id)
            return ComplianceJobStatus.FAILED
        except (TypeError, ValueError):
            await self.fail_job(
                job_id,
                error_code=COMPLIANCE_VALIDATION_FAILED,
                error_message=("Compliance validation could not be completed."),
            )
            logger.exception("Compliance validation failed for %s.", job_id)
            return ComplianceJobStatus.FAILED
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            await self.fail_job(
                job_id,
                error_code=COMPLIANCE_VALIDATION_FAILED,
                error_message=("Compliance validation could not be completed."),
            )
            logger.exception(
                "Unexpected compliance worker failure for %s.",
                job_id,
            )
            return ComplianceJobStatus.FAILED

    async def _start_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
        allow_redelivery: bool = False,
    ) -> tuple[ComplianceJob | None, bool]:
        job = await ComplianceJobRepository(session).get_by_id(
            job_id,
            for_update=True,
        )
        if job is None or job.status in TERMINAL_COMPLIANCE_JOB_STATUSES:
            return job, False
        if job.status is ComplianceJobStatus.CANCEL_REQUESTED:
            return job, False
        details = dict(job.error_details_json or {})
        same_worker_retry = (
            details.get("workerReference") == worker_reference
            and attempt_number > job.attempt_number
        )
        same_worker_redelivery = (
            allow_redelivery
            and details.get("workerReference") == worker_reference
            and attempt_number == job.attempt_number
        )
        if (
            job.status is not ComplianceJobStatus.QUEUED
            and not same_worker_retry
            and not same_worker_redelivery
        ):
            return job, False
        job.status = ComplianceJobStatus.LOADING_CONTEXT
        job.progress = max(job.progress, 5)
        job.current_stage = "Loading retained validation context"
        job.started_at = job.started_at or utc_now()
        job.attempt_number = min(
            max(1, attempt_number),
            job.maximum_attempts,
        )
        details["workerReference"] = worker_reference
        details["workerAttempt"] = attempt_number
        job.error_details_json = details
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.START_COMPLIANCE_VALIDATION,
            entity_type="ComplianceJob",
            entity_id=job.id,
            description="Compliance worker started validation.",
            new_values={
                "attemptNumber": job.attempt_number,
                "documentFileId": str(job.document_file_id),
            },
        )
        await session.commit()
        return job, True

    @asynccontextmanager
    async def _execution_lease(
        self,
        job_id: UUID,
    ) -> AsyncIterator[bool]:
        """Hold one lease across commits; PostgreSQL releases it on crash."""

        bind = getattr(self.session_factory, "kw", {}).get("bind")
        if bind is not None and bind.dialect.name == "postgresql":
            lease_key = job_id.int & ((1 << 64) - 1)
            if lease_key >= 1 << 63:
                lease_key -= 1 << 64
            async with bind.connect() as connection:
                acquired = bool(
                    await connection.scalar(
                        sql_text("SELECT pg_try_advisory_lock(:lease_key)"),
                        {"lease_key": lease_key},
                    )
                )
                try:
                    yield acquired
                finally:
                    if acquired:
                        try:
                            await connection.execute(
                                sql_text("SELECT pg_advisory_unlock(:lease_key)"),
                                {"lease_key": lease_key},
                            )
                        except SQLAlchemyError:
                            logger.exception(
                                "Unable to release compliance lease for %s.",
                                job_id,
                            )
            return

        with _LOCAL_LEASE_GUARD:
            acquired = job_id not in _LOCAL_LEASES
            if acquired:
                _LOCAL_LEASES.add(job_id)
        try:
            yield acquired
        finally:
            if acquired:
                with _LOCAL_LEASE_GUARD:
                    _LOCAL_LEASES.discard(job_id)

    async def _load_context(
        self,
        session: AsyncSession,
        job: ComplianceJob,
    ):
        files = DocumentFileRepository(session)
        extraction_runs = ExtractionRunRepository(session)
        ocr_runs = OCRRunRepository(session)
        language_runs = LanguageDetectionRunRepository(session)
        document_file = await files.get_by_id(job.document_file_id)
        extraction = await extraction_runs.get_by_id(job.extraction_run_id)
        ocr = (
            await ocr_runs.get_by_id(job.ocr_run_id)
            if job.ocr_run_id is not None
            else None
        )
        language = await language_runs.get_by_id(job.language_detection_run_id)
        rule = await ValidationRuleRepository(session).get_by_id(job.validation_rule_id)
        if document_file is None or extraction is None or language is None:
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                "A retained compliance prerequisite is no longer available.",
            )
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
            or document_file.deleted_at is not None
            or document_file.document.is_archived
        ):
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                "Only a current available document file can be validated.",
            )
        if (
            document_file.latest_extraction_run_id != extraction.id
            or document_file.latest_language_detection_run_id != language.id
            or (
                job.ocr_run_id is not None
                and document_file.latest_ocr_run_id != job.ocr_run_id
            )
        ):
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                "The selected compliance source is no longer current.",
            )
        if (
            extraction.document_file_id != document_file.id
            or extraction.status not in _USABLE_EXTRACTION_STATUSES
            or language.document_file_id != document_file.id
            or language.extraction_run_id != extraction.id
            or language.status not in _USABLE_LANGUAGE_STATUSES
            or language.source_content_hash != job.source_content_hash
        ):
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                "The selected extraction and language runs are incompatible.",
            )
        if extraction.requires_ocr:
            if (
                ocr is None
                or ocr.status not in _USABLE_OCR_STATUSES
                or ocr.document_file_id != document_file.id
                or ocr.source_extraction_run_id != extraction.id
                or language.ocr_run_id != ocr.id
            ):
                raise ComplianceWorkerError(
                    "COMPLIANCE_OCR_REQUIRED",
                    "A compatible completed OCR run is required.",
                )
        elif ocr is not None and (
            ocr.document_file_id != document_file.id
            or ocr.source_extraction_run_id != extraction.id
            or language.ocr_run_id != ocr.id
        ):
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_NOT_AVAILABLE",
                "The selected OCR run is incompatible.",
            )
        if rule is None or not rule.is_active:
            raise ComplianceWorkerError(
                "COMPLIANCE_RULE_NOT_FOUND",
                "The selected validation rule is not active.",
            )

        blocks = await LanguageBlockResultRepository(session).list_compliance_sources(
            language.id,
            limit=self.settings.compliance_max_blocks + 1,
        )
        if len(blocks) > self.settings.compliance_max_blocks:
            raise ComplianceWorkerError(
                "COMPLIANCE_BLOCK_LIMIT_EXCEEDED",
                "The source exceeds the configured compliance block limit.",
            )
        if not blocks:
            raise ComplianceWorkerError(
                "COMPLIANCE_SOURCE_EMPTY",
                "No retained language-annotated content is available.",
            )
        table_limit = max(1, extraction.total_tables)
        tables, table_total = await ExtractedTableRepository(session).list(
            extraction.id,
            include_cells=True,
            page=1,
            page_size=table_limit,
        )
        if table_total > table_limit:
            raise ComplianceWorkerError(
                "COMPLIANCE_TABLE_LIMIT_EXCEEDED",
                "The extracted table set could not be loaded completely.",
            )

        profiles = SectionAliasProfileRepository(session)
        profile = (
            await profiles.get_by_id(rule.section_alias_profile_id)
            if rule.section_alias_profile_id is not None
            else await profiles.get_default()
        )
        aliases = []
        if profile is not None and profile.is_active:
            aliases = await SectionAliasRepository(session).list_active_for_profile(
                profile.id
            )
        alias_data = [
            SectionAliasData(
                id=alias.id,
                profile_id=alias.section_definition.profile_id,
                section_definition_id=alias.section_definition_id,
                canonical_code=alias.section_definition.canonical_code,
                language_code=alias.language_code.value,
                alias_text=alias.alias_text,
                normalised_alias=alias.normalised_alias,
                match_type=alias.match_type.value,
                priority=alias.priority,
                is_regex=alias.is_regex,
                is_active=alias.is_active,
                display_order=alias.section_definition.display_order,
                is_repeatable=alias.section_definition.is_repeatable,
            )
            for alias in aliases
        ]
        expected_code = document_file.revision.full_document_code
        source_code = self._source_document_code(
            expected_code,
            document_file.document.base_document_code,
            document_file.original_filename,
            blocks,
        )
        rule_snapshot = self.contexts.snapshot_rule(rule)
        validation_options = dict(rule_snapshot.validation_options)
        validation_options.setdefault(
            "translation_group_min_confidence",
            self.settings.translation_group_min_confidence,
        )
        rule_snapshot = rule_snapshot.model_copy(
            update={"validation_options": validation_options},
            deep=True,
        )
        context = self.contexts.build(
            rule=rule_snapshot,
            source_format=document_file.file_extension,
            blocks=blocks,
            tables=tables,
            section_aliases=alias_data,
            language_results=blocks,
            prerequisites={
                "extractionAvailable": True,
                "extractionStatus": extraction.status.value,
                "ocrRequired": extraction.requires_ocr,
                "ocrCompleted": (
                    not extraction.requires_ocr
                    or (ocr is not None and ocr.status in _USABLE_OCR_STATUSES)
                ),
                "ocrConfidenceTooLow": bool(
                    ocr is not None
                    and ocr.average_confidence is not None
                    and float(ocr.average_confidence)
                    < self.settings.ocr_review_confidence_threshold
                ),
                "languageDetectionAvailable": True,
                "languageDetectionStatus": language.status.value,
                "contextComplete": True,
            },
            warnings=[
                *[str(item) for item in extraction.warnings_json],
                *[str(item) for item in language.warnings_json],
            ],
            document_id=job.document_id,
            document_revision_id=job.document_revision_id,
            document_file_id=job.document_file_id,
            extraction_run_id=extraction.id,
            ocr_run_id=ocr.id if ocr is not None else None,
            language_detection_run_id=language.id,
            document_code=source_code,
            expected_document_code=expected_code,
            source_content_hash=job.source_content_hash,
        )
        previous = await ComplianceRunRepository(session).get_latest_for_file(
            job.document_file_id
        )
        previous_findings = await self._load_previous_findings(
            session,
            previous,
        )
        return context, previous_findings

    async def _load_previous_findings(
        self,
        session: AsyncSession,
        previous: ComplianceRun | None,
    ) -> list[ValidationFinding]:
        if previous is None:
            return []
        finding_repository = ValidationFindingRepository(session)
        total = await finding_repository.count_for_run(previous.id)
        if total > self.settings.compliance_max_blocks:
            raise ComplianceWorkerError(
                "COMPLIANCE_FINDING_LIMIT_EXCEEDED",
                (
                    "The previous result exceeds the configured "
                    "compliance evidence limit."
                ),
            )
        if total == 0:
            return []
        return await finding_repository.list_for_run(
            previous.id,
            page=1,
            page_size=total,
        )

    @staticmethod
    def _source_document_code(
        expected: str,
        base_code: str,
        filename: str,
        blocks,
    ) -> str | None:
        haystacks = [filename, *[block.text[:2000] for block in blocks[:50]]]
        expected_folded = expected.casefold()
        base_folded = base_code.casefold()
        for text in haystacks:
            folded = text.casefold()
            if expected_folded in folded:
                return expected
            if base_folded in folded:
                return base_code
        return None

    async def _set_progress(
        self,
        session: AsyncSession,
        job: ComplianceJob,
        *,
        status: ComplianceJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        result = await session.execute(
            update(ComplianceJob)
            .where(
                ComplianceJob.id == job.id,
                ComplianceJob.status != ComplianceJobStatus.CANCEL_REQUESTED,
                ComplianceJob.status.not_in(list(TERMINAL_COMPLIANCE_JOB_STATUSES)),
            )
            .values(
                status=status,
                progress=progress,
                current_stage=stage,
            )
        )
        await session.commit()
        await session.refresh(job)
        if cast(CursorResult[Any], result).rowcount != 1:
            if job.status is ComplianceJobStatus.CANCEL_REQUESTED:
                raise CompliancePipelineCancelled(
                    "Compliance validation was cancelled."
                )
            raise ComplianceWorkerError(
                "COMPLIANCE_JOB_NOT_ACTIVE",
                "The compliance job is no longer active.",
            )

    async def _cancel(
        self,
        session: AsyncSession,
        job: ComplianceJob,
    ) -> ComplianceJobStatus:
        job.status = ComplianceJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = utc_now()
        await AuditLogRepository(session).create(
            user_id=job.requested_by,
            action=AuditAction.CANCEL_COMPLIANCE_VALIDATION,
            entity_type="ComplianceJob",
            entity_id=job.id,
            description="Compliance validation was cancelled.",
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
        """Mark failure without exposing tracebacks or storage paths."""

        try:
            async with self.session_factory() as session:
                job = await ComplianceJobRepository(session).get_by_id(
                    job_id,
                    for_update=True,
                )
                if job is None or job.status in TERMINAL_COMPLIANCE_JOB_STATUSES:
                    return
                job.status = ComplianceJobStatus.FAILED
                job.current_stage = "Failed"
                job.failed_at = utc_now()
                job.error_code = error_code[:100]
                job.error_message = error_message[:2000]
                await AuditLogRepository(session).create(
                    user_id=job.requested_by,
                    action=AuditAction.FAIL_COMPLIANCE_VALIDATION,
                    entity_type="ComplianceJob",
                    entity_id=job.id,
                    description="Compliance validation failed.",
                    new_values={
                        "documentFileId": str(job.document_file_id),
                        "errorCode": job.error_code,
                    },
                )
                await session.commit()
        except SQLAlchemyError:
            logger.exception(
                "Unable to mark compliance job %s as failed.",
                job_id,
            )
