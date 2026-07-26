"""Bounded background orchestration for revision comparison jobs."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.models.document_file import DocumentFile
from app.models.revision_comparison_job import (
    TERMINAL_REVISION_COMPARISON_JOB_STATUSES,
    RevisionComparisonJob,
    RevisionComparisonJobStatus,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.revision_change_repository import (
    RevisionChangeRepository,
)
from app.repositories.revision_comparison_job_repository import (
    RevisionComparisonJobRepository,
)
from app.repositories.revision_comparison_repository import (
    RevisionComparisonRepository,
)
from app.services.revision_comparison.revision_alignment_service import (
    RevisionAlignmentService,
)
from app.services.revision_comparison.revision_change_detection_service import (
    RevisionChangeDetectionService,
)
from app.services.revision_comparison.revision_comparison_persistence_service import (
    RevisionComparisonPersistenceService,
)
from app.services.revision_comparison.revision_context_service import (
    RevisionContextError,
    RevisionContextService,
)
from app.services.revision_comparison.revision_finding_comparison_service import (
    RevisionFindingComparisonService,
)
from app.services.revision_comparison.revision_language_comparison_service import (
    RevisionLanguageComparisonService,
)
from app.services.revision_comparison.revision_score_comparison_service import (
    RevisionScoreComparisonService,
)
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class RevisionComparisonWorkerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TransientRevisionComparisonWorkerError(RuntimeError):
    """Infrastructure failure eligible for a bounded Celery retry."""


class RevisionComparisonWorkerService:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.alignment = RevisionAlignmentService(
            fuzzy_threshold=settings.revision_alignment_fuzzy_threshold
        )
        self.detector = RevisionChangeDetectionService(
            snapshot_max_characters=settings.report_text_snippet_max_characters
        )
        self.languages = RevisionLanguageComparisonService()
        self.findings = RevisionFindingComparisonService()
        self.scores = RevisionScoreComparisonService()

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> RevisionComparisonJobStatus:
        try:
            async with self.session_factory() as session:
                jobs = RevisionComparisonJobRepository(session)
                job = await jobs.get_by_id(job_id, for_update=True)
                if job is None:
                    return RevisionComparisonJobStatus.FAILED
                if job.status in TERMINAL_REVISION_COMPARISON_JOB_STATUSES:
                    return job.status
                if job.status is RevisionComparisonJobStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, job)
                job.attempt_number = min(
                    max(1, attempt_number), job.maximum_attempts
                )
                job.status = RevisionComparisonJobStatus.LOADING_REVISIONS
                job.progress = 5
                job.current_stage = "Loading retained revision contexts"
                job.started_at = job.started_at or utc_now()
                job.error_details_json = {"workerReference": worker_reference}
                await session.commit()

                files = DocumentFileRepository(session)
                base_file = await files.get_by_id(
                    job.base_document_file_id
                )
                target_file = await files.get_by_id(
                    job.target_document_file_id
                )
                if base_file is None or target_file is None:
                    raise RevisionComparisonWorkerError(
                        "REVISION_COMPARISON_FILE_UNAVAILABLE",
                        "One of the retained revision files is unavailable.",
                    )
                self._validate_job_files(job, base_file, target_file)
                contexts = RevisionContextService(
                    session,
                    maximum_blocks=self.settings.revision_comparison_max_blocks,
                )
                base = await contexts.build(base_file)
                target = await contexts.build(target_file)
                if await self._cancel_requested(session, job):
                    return await self._cancel(session, job)

                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.ALIGNING_SECTIONS,
                    20,
                    "Aligning canonical sections and containers",
                )
                pairs = self.alignment.align(base.items, target.items)
                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.ALIGNING_GROUPS,
                    35,
                    "Aligning translation groups and blocks",
                )
                if await self._cancel_requested(session, job):
                    return await self._cancel(session, job)

                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.COMPARING_CONTENT,
                    50,
                    "Classifying bounded content changes",
                )
                changes = self.detector.detect(pairs)
                if len(changes) > self.settings.revision_comparison_max_changes:
                    raise RevisionComparisonWorkerError(
                        "REVISION_COMPARISON_CHANGE_LIMIT",
                        "The comparison exceeds the configured change limit.",
                    )

                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.COMPARING_LANGUAGES,
                    65,
                    "Comparing Indonesian, English, and Chinese coverage",
                )
                language_summary = self.languages.summarize(
                    changes,
                    base_language_counts=base.language_counts,
                    target_language_counts=target.language_counts,
                    base_language_coverage=base.language_coverage,
                    target_language_coverage=target.language_coverage,
                )

                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.COMPARING_FINDINGS,
                    78,
                    "Comparing retained finding evidence",
                )
                finding_changes, finding_summary = self.findings.compare(
                    base.findings, target.findings
                )
                classification = self.scores.classify(
                    compliance_delta=self._delta(
                        base.compliance_score, target.compliance_score
                    ),
                    similarity_delta=self._delta(
                        base.similarity_score, target.similarity_score
                    ),
                    glossary_violation_delta=self._int_delta(
                        base.glossary_violation_count,
                        target.glossary_violation_count,
                    ),
                    open_finding_delta=(
                        target.open_finding_count
                        - base.open_finding_count
                    ),
                    critical_finding_delta=(
                        target.critical_open_finding_count
                        - base.critical_open_finding_count
                    ),
                )
                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.CALCULATING_SUMMARY,
                    88,
                    "Calculating non-mutating comparison summary",
                )
                warnings: list[str] = []
                if (
                    base.compliance_run_id is None
                    or target.compliance_run_id is None
                ):
                    warnings.append(
                        "Compliance comparison is not evaluated for one or "
                        "both revisions."
                    )
                if (
                    base.similarity_run_id is None
                    or target.similarity_run_id is None
                ):
                    warnings.append(
                        "Translation similarity comparison is not evaluated "
                        "for one or both revisions."
                    )
                if (
                    base.glossary_run_id is None
                    or target.glossary_run_id is None
                ):
                    warnings.append(
                        "Glossary comparison is not evaluated for one or "
                        "both revisions."
                    )
                if await self._cancel_requested(session, job):
                    return await self._cancel(session, job)

                await self._stage(
                    session,
                    job,
                    RevisionComparisonJobStatus.PERSISTING,
                    95,
                    "Persisting comparison and bounded snippets",
                )
                persistence = RevisionComparisonPersistenceService(
                    RevisionComparisonRepository(session),
                    RevisionChangeRepository(session),
                    batch_size=self.settings.revision_comparison_db_batch_size,
                )
                comparison = await persistence.persist(
                    job=job,
                    base=base,
                    target=target,
                    pairs=pairs,
                    detected_changes=changes,
                    language_summary=language_summary,
                    finding_changes=finding_changes,
                    finding_summary=finding_summary,
                    classification=classification,
                    warnings=warnings,
                )
                job.status = (
                    RevisionComparisonJobStatus.PARTIALLY_COMPLETED
                    if warnings
                    else RevisionComparisonJobStatus.COMPLETED
                )
                job.progress = 100
                job.current_stage = "Completed"
                job.completed_at = utc_now()
                job.result_summary_json = {
                    "comparisonId": str(comparison.id),
                    "classification": classification.value,
                    "totalChanges": comparison.total_changes,
                    "added": comparison.added_blocks,
                    "removed": comparison.removed_blocks,
                    "modified": comparison.modified_blocks,
                    "languageRegressions": sum(
                        1
                        for item in language_summary
                        if item.get("regression") is True
                    ),
                }
                await AuditLogRepository(session).create(
                    action=AuditAction.COMPLETE_REVISION_COMPARISON,
                    description="Revision comparison completed.",
                    user_id=job.requested_by,
                    entity_type="RevisionComparison",
                    entity_id=comparison.id,
                    new_values=job.result_summary_json,
                )
                await session.commit()
                return job.status
        except RevisionContextError as exc:
            await self.fail_job(
                job_id,
                error_code="REVISION_COMPARISON_PREREQUISITE_INVALID",
                error_message=str(exc),
            )
            return RevisionComparisonJobStatus.FAILED
        except RevisionComparisonWorkerError as exc:
            await self.fail_job(
                job_id, error_code=exc.code, error_message=str(exc)
            )
            return RevisionComparisonJobStatus.FAILED
        except SQLAlchemyError as exc:
            raise TransientRevisionComparisonWorkerError(
                "The revision comparison database operation failed."
            ) from exc
        except Exception:
            logger.exception(
                "Unexpected revision comparison worker failure",
                extra={"job_id": str(job_id)},
            )
            await self.fail_job(
                job_id,
                error_code="REVISION_COMPARISON_UNEXPECTED_ERROR",
                error_message=(
                    "Revision comparison failed unexpectedly. Review the "
                    "worker logs for diagnostic details."
                ),
            )
            return RevisionComparisonJobStatus.FAILED

    async def fail_job(
        self, job_id: UUID, *, error_code: str, error_message: str
    ) -> None:
        async with self.session_factory() as session:
            job = await RevisionComparisonJobRepository(session).get_by_id(
                job_id, for_update=True
            )
            if job is None or job.status in (
                TERMINAL_REVISION_COMPARISON_JOB_STATUSES
            ):
                return
            job.status = RevisionComparisonJobStatus.FAILED
            job.progress = min(job.progress, 99)
            job.current_stage = "Failed"
            job.failed_at = utc_now()
            job.error_code = error_code[:100]
            job.error_message = error_message[:2000]
            await AuditLogRepository(session).create(
                action=AuditAction.FAIL_REVISION_COMPARISON,
                description="Revision comparison failed.",
                user_id=job.requested_by,
                entity_type="RevisionComparisonJob",
                entity_id=job.id,
                new_values={"errorCode": job.error_code},
            )
            await session.commit()

    @staticmethod
    async def _stage(
        session: AsyncSession,
        job: RevisionComparisonJob,
        status: RevisionComparisonJobStatus,
        progress: int,
        stage: str,
    ) -> None:
        job.status = status
        job.progress = progress
        job.current_stage = stage
        await session.commit()

    @staticmethod
    async def _cancel_requested(
        session: AsyncSession, job: RevisionComparisonJob
    ) -> bool:
        await session.refresh(job, attribute_names=["status"])
        return job.status is RevisionComparisonJobStatus.CANCEL_REQUESTED

    @staticmethod
    async def _cancel(
        session: AsyncSession, job: RevisionComparisonJob
    ) -> RevisionComparisonJobStatus:
        job.status = RevisionComparisonJobStatus.CANCELLED
        job.current_stage = "Cancelled"
        job.cancelled_at = utc_now()
        await AuditLogRepository(session).create(
            action=AuditAction.CANCEL_REVISION_COMPARISON,
            description="Revision comparison cancelled.",
            user_id=job.requested_by,
            entity_type="RevisionComparisonJob",
            entity_id=job.id,
        )
        await session.commit()
        return job.status

    @staticmethod
    def _validate_job_files(
        job: RevisionComparisonJob,
        base_file: DocumentFile,
        target_file: DocumentFile,
    ) -> None:
        """Reject corrupt/tampered jobs before reading retained content."""

        if (
            base_file.id != job.base_document_file_id
            or target_file.id != job.target_document_file_id
            or base_file.document_id != job.document_id
            or target_file.document_id != job.document_id
            or base_file.document_revision_id != job.base_revision_id
            or target_file.document_revision_id != job.target_revision_id
        ):
            raise RevisionComparisonWorkerError(
                "REVISION_COMPARISON_FILE_SCOPE_MISMATCH",
                "The retained files do not match the requested document "
                "revisions.",
            )

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return right - left

    @staticmethod
    def _int_delta(left: int | None, right: int | None) -> int | None:
        if left is None or right is None:
            return None
        return right - left
