"""Queue, execute, and query Phase 9 revision comparisons."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.extraction_run import ExtractionRun
from app.models.revision_change import (
    RevisionChange,
    RevisionChangeType,
    RevisionEntityType,
)
from app.models.revision_comparison import RevisionComparison
from app.models.revision_comparison_job import (
    TERMINAL_REVISION_COMPARISON_JOB_STATUSES,
    RevisionComparisonJob,
    RevisionComparisonJobStatus,
    RevisionComparisonJobType,
)
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.repositories.revision_change_repository import (
    RevisionChangeRepository,
)
from app.repositories.revision_comparison_job_repository import (
    RevisionComparisonJobRepository,
)
from app.repositories.revision_comparison_repository import (
    RevisionComparisonRepository,
)
from app.schemas.revision_comparison import (
    RevisionChangeListResponse,
    RevisionChangeResponse,
    RevisionComparisonHistoryResponse,
    RevisionComparisonJobListResponse,
    RevisionComparisonJobResponse,
    RevisionComparisonQueuedResponse,
    RevisionComparisonResponse,
    RevisionComparisonSummaryResponse,
    RevisionFindingChange,
    RevisionFindingChangesResponse,
    RevisionLanguageChange,
    RevisionLanguageChangesResponse,
    RevisionSectionChange,
    RevisionSectionChangesResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import DocumentServiceBase, document_error
from app.utils.datetime import utc_now


def revision_comparison_not_found() -> Exception:
    return document_error(
        "The revision comparison does not exist or is outside your scope.",
        code="REVISION_COMPARISON_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Revision comparison was not found.",
    )


def revision_comparison_job_not_found() -> Exception:
    return document_error(
        "The revision comparison job does not exist or is outside your scope.",
        code="REVISION_COMPARISON_JOB_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Revision comparison job was not found.",
    )


class RevisionComparisonJobService(DocumentServiceBase):
    """Validate same-document prerequisites and enqueue worker work."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)
        self.files = DocumentFileRepository(session)
        self.jobs = RevisionComparisonJobRepository(session)
        self.comparisons = RevisionComparisonRepository(session)

    async def start(
        self,
        *,
        document_id: UUID,
        base_revision_id: UUID,
        target_revision_id: UUID,
        force: bool,
    ) -> RevisionComparisonQueuedResponse:
        self._ensure_permission(Permission.REVISION_COMPARISON_RUN)
        if base_revision_id == target_revision_id:
            raise document_error(
                "Base and target revisions must be different.",
                field="targetRevisionId",
                code="REVISION_COMPARISON_SAME_REVISION",
            )
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise revision_comparison_not_found()
        self._ensure_document_scope(document)
        base_revision = await self.revisions.get_by_id(
            base_revision_id, document_id=document_id
        )
        target_revision = await self.revisions.get_by_id(
            target_revision_id, document_id=document_id
        )
        if base_revision is None or target_revision is None:
            raise document_error(
                "Both revisions must belong to the selected document.",
                code="REVISION_COMPARISON_DIFFERENT_DOCUMENT",
                title="Revision comparison prerequisites are invalid.",
            )
        base_file = await self.files.get_current_by_revision(
            base_revision.id, for_update=True
        )
        target_file = await self.files.get_current_by_revision(
            target_revision.id, for_update=True
        )
        self._validate_file_prerequisites(base_file, "baseRevisionId")
        self._validate_file_prerequisites(target_file, "targetRevisionId")
        assert base_file is not None and target_file is not None
        self._validate_file_ownership(
            base_file, document.id, base_revision.id, "baseRevisionId"
        )
        self._validate_file_ownership(
            target_file,
            document.id,
            target_revision.id,
            "targetRevisionId",
        )
        base_content_hash = await self._content_hash(
            base_file, "baseRevisionId"
        )
        target_content_hash = await self._content_hash(
            target_file, "targetRevisionId"
        )

        active = await self.jobs.get_active_pair(
            document_id, base_revision.id, target_revision.id
        )
        if active is not None:
            raise document_error(
                "An active comparison already exists for these revisions.",
                code="REVISION_COMPARISON_ACTIVE_JOB_EXISTS",
                status_code=HTTPStatus.CONFLICT,
                title="Revision comparison is already running.",
            )
        if not force:
            equivalent = await self.comparisons.find_equivalent(
                document_id=document_id,
                base_revision_id=base_revision.id,
                target_revision_id=target_revision.id,
                base_content_hash=base_content_hash,
                target_content_hash=target_content_hash,
            )
            if equivalent is not None:
                return RevisionComparisonQueuedResponse(
                    job_id=equivalent.revision_comparison_job_id,
                    status=RevisionComparisonJobStatus.COMPLETED,
                    progress=100,
                    comparison_id=equivalent.id,
                    reused_existing_result=True,
                )

        job = RevisionComparisonJob(
            document_id=document.id,
            base_revision_id=base_revision.id,
            target_revision_id=target_revision.id,
            base_document_file_id=base_file.id,
            target_document_file_id=target_file.id,
            job_type=(
                RevisionComparisonJobType.REANALYSIS
                if force
                else RevisionComparisonJobType.INITIAL
            ),
            status=RevisionComparisonJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            requested_by=self.user.id,
            requested_at=utc_now(),
            maximum_attempts=self.settings.revision_comparison_max_retries
            + 1,
        )
        try:
            await self.jobs.add(job)
            await self.audit(
                action=AuditAction.QUEUE_REVISION_COMPARISON,
                entity_type="RevisionComparisonJob",
                entity_id=job.id,
                description="Revision comparison queued.",
                new_values={
                    "documentId": str(document.id),
                    "baseRevisionId": str(base_revision.id),
                    "targetRevisionId": str(target_revision.id),
                    "force": force,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_error(
                "An active comparison already exists for these revisions.",
                code="REVISION_COMPARISON_ACTIVE_JOB_EXISTS",
                status_code=HTTPStatus.CONFLICT,
                title="Revision comparison is already running.",
            ) from exc
        self._dispatch(job.id)
        return RevisionComparisonQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            comparison_id=None,
            reused_existing_result=False,
        )

    async def get(self, job_id: UUID) -> RevisionComparisonJobResponse:
        self._ensure_permission(Permission.REVISION_COMPARISON_VIEW)
        job = await self.jobs.get_by_id(
            job_id, department_ids=self._scope_department_ids()
        )
        if job is None:
            raise revision_comparison_job_not_found()
        return revision_job_response(job)

    async def list(
        self,
        *,
        document_id: UUID | None,
        statuses: Sequence[RevisionComparisonJobStatus] | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
    ) -> RevisionComparisonJobListResponse:
        self._ensure_permission(Permission.REVISION_COMPARISON_VIEW)
        items, total = await self.jobs.list_page(
            department_ids=self._scope_department_ids(),
            document_id=document_id,
            statuses=statuses,
            requested_from=requested_from,
            requested_to=requested_to,
            page=page,
            page_size=page_size,
        )
        return RevisionComparisonJobListResponse(
            items=[revision_job_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def cancel(self, job_id: UUID) -> RevisionComparisonJobResponse:
        self._ensure_permission(Permission.REVISION_COMPARISON_RUN)
        job = await self.jobs.get_by_id(
            job_id,
            department_ids=self._scope_department_ids(),
            for_update=True,
        )
        if job is None:
            raise revision_comparison_job_not_found()
        if job.status in TERMINAL_REVISION_COMPARISON_JOB_STATUSES:
            raise document_error(
                "A terminal revision comparison cannot be cancelled.",
                code="REVISION_COMPARISON_ALREADY_TERMINAL",
                status_code=HTTPStatus.CONFLICT,
            )
        job.status = RevisionComparisonJobStatus.CANCEL_REQUESTED
        job.current_stage = "Cancellation requested"
        await self.audit(
            action=AuditAction.CANCEL_REVISION_COMPARISON,
            entity_type="RevisionComparisonJob",
            entity_id=job.id,
            description="Revision comparison cancellation requested.",
        )
        await self.session.commit()
        return revision_job_response(job)

    def _dispatch(self, job_id: UUID) -> None:
        from app.workers.celery_app import celery_app

        celery_app.send_task(
            (
                "app.workers.revision_comparison_tasks."
                "process_revision_comparison_job"
            ),
            args=[str(job_id)],
            queue=self.settings.revision_comparison_queue_name,
        )

    @staticmethod
    def _validate_file_prerequisites(
        document_file: DocumentFile | None, field: str
    ) -> None:
        if document_file is None:
            raise document_error(
                "The revision has no current available primary file.",
                field=field,
                code="REVISION_COMPARISON_FILE_REQUIRED",
                status_code=HTTPStatus.CONFLICT,
            )
        if document_file.latest_extraction_run_id is None:
            raise document_error(
                "Run extraction before comparing this revision.",
                field=field,
                code="REVISION_COMPARISON_EXTRACTION_REQUIRED",
                status_code=HTTPStatus.CONFLICT,
                title="Revision comparison prerequisites are incomplete.",
            )

    @staticmethod
    def _validate_file_ownership(
        document_file: DocumentFile,
        document_id: UUID,
        revision_id: UUID,
        field: str,
    ) -> None:
        if (
            document_file.document_id != document_id
            or document_file.document_revision_id != revision_id
        ):
            raise document_error(
                "The current file does not belong to the selected revision.",
                field=field,
                code="REVISION_COMPARISON_FILE_SCOPE_MISMATCH",
                status_code=HTTPStatus.CONFLICT,
                title="Revision comparison prerequisites are invalid.",
            )

    async def _content_hash(
        self, document_file: DocumentFile, field: str
    ) -> str:
        run_id = document_file.latest_extraction_run_id
        assert run_id is not None
        extraction = await self.session.get(ExtractionRun, run_id)
        if (
            extraction is None
            or extraction.document_id != document_file.document_id
            or extraction.document_revision_id
            != document_file.document_revision_id
            or extraction.document_file_id != document_file.id
        ):
            raise document_error(
                "The latest extraction run is unavailable or incompatible.",
                field=field,
                code="REVISION_COMPARISON_EXTRACTION_INCOMPATIBLE",
                status_code=HTTPStatus.CONFLICT,
                title="Revision comparison prerequisites are incomplete.",
            )
        return (
            extraction.content_hash
            or extraction.source_sha256_hash
            or document_file.sha256_hash
        )

    def _scope_department_ids(self) -> builtins.list[UUID] | None:
        if has_permission(
            self.user.role,
            Permission.REVISION_COMPARISON_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        ):
            return None
        return [self.user.department_id] if self.user.department_id else []

    def _ensure_document_scope(self, document: Document) -> None:
        scope = self._scope_department_ids()
        if scope is not None and document.department_id not in scope:
            raise AuthorizationError(
                "This document is outside your department scope."
            )

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError(
                "You do not have permission to perform this action."
            )


class RevisionComparisonQueryService(RevisionComparisonJobService):
    """Scoped retained result and child-change reads."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, settings, user, metadata)
        self.changes = RevisionChangeRepository(session)

    async def get_comparison(
        self, comparison_id: UUID
    ) -> RevisionComparisonResponse:
        comparison = await self._comparison(comparison_id)
        return revision_comparison_response(comparison)

    async def summary(
        self, comparison_id: UUID
    ) -> RevisionComparisonSummaryResponse:
        comparison = await self._comparison(comparison_id)
        return RevisionComparisonSummaryResponse(
            comparison_id=comparison.id,
            classification=comparison.classification,
            total_changes=comparison.total_changes,
            added=comparison.added_blocks,
            removed=comparison.removed_blocks,
            modified=comparison.modified_blocks,
            moved=comparison.moved_blocks,
            unchanged=comparison.unchanged_blocks,
            compliance_score_change=self._float(
                comparison.compliance_score_change
            ),
            similarity_score_change=self._float(
                comparison.similarity_score_change
            ),
            new_findings=comparison.new_findings,
            no_longer_reproduced=comparison.removed_findings,
            summary=comparison.summary_json,
            warnings=list(comparison.warnings_json),
        )

    async def list_changes(
        self,
        comparison_id: UUID,
        *,
        change_types: Sequence[RevisionChangeType] | None,
        entity_types: Sequence[RevisionEntityType] | None,
        language_code: str | None,
        section_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> RevisionChangeListResponse:
        await self._comparison(comparison_id)
        items, total = await self.changes.list_page(
            comparison_id,
            change_types=change_types,
            entity_types=entity_types,
            language_code=language_code,
            section_id=section_id,
            search=search,
            page=page,
            page_size=page_size,
        )
        return RevisionChangeListResponse(
            items=[revision_change_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def section_changes(
        self, comparison_id: UUID
    ) -> RevisionSectionChangesResponse:
        comparison = await self._comparison(comparison_id)
        rows = await self.changes.list_all(
            comparison_id,
            maximum=self.settings.revision_comparison_max_changes,
        )
        groups: dict[str, dict[str, int]] = {}
        for row in rows:
            key = str(
                row.metadata_json.get("targetSectionCode")
                or row.metadata_json.get("baseSectionCode")
                or "UNMAPPED"
            )
            counts = groups.setdefault(
                key,
                {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "moved": 0,
                    "unchanged": 0,
                },
            )
            bucket = {
                RevisionChangeType.ADDED: "added",
                RevisionChangeType.REMOVED: "removed",
                RevisionChangeType.MODIFIED: "modified",
                RevisionChangeType.MOVED: "moved",
                RevisionChangeType.UNCHANGED: "unchanged",
                RevisionChangeType.SPLIT: "modified",
                RevisionChangeType.MERGED: "modified",
            }[row.change_type]
            counts[bucket] += 1
        return RevisionSectionChangesResponse(
            comparison_id=comparison.id,
            items=[
                RevisionSectionChange(section_key=key, **counts)
                for key, counts in sorted(groups.items())
            ],
        )

    async def languages(
        self, comparison_id: UUID
    ) -> RevisionLanguageChangesResponse:
        comparison = await self._comparison(comparison_id)
        values = comparison.language_coverage_change_json.get(
            "languages", []
        )
        items = [
            RevisionLanguageChange(
                language_code=cast(
                    Literal["id", "en", "zh", "unknown"],
                    str(item.get("languageCode", "unknown")),
                ),
                base_count=int(item.get("baseCount", 0)),
                target_count=int(item.get("targetCount", 0)),
                base_coverage=self._optional_float(
                    item.get("baseCoverage")
                ),
                target_coverage=self._optional_float(
                    item.get("targetCoverage")
                ),
                coverage_change=self._optional_float(
                    item.get("coverageChange")
                ),
                additions=int(item.get("additions", 0)),
                removals=int(item.get("removals", 0)),
                modifications=int(item.get("modifications", 0)),
                base_presence=bool(item.get("basePresence", False)),
                target_presence=bool(item.get("targetPresence", False)),
                regression=bool(item.get("regression", False)),
                fixed_missing_language=bool(
                    item.get("fixedMissingLanguage", False)
                ),
            )
            for item in values
            if isinstance(item, dict)
        ]
        return RevisionLanguageChangesResponse(
            comparison_id=comparison.id,
            items=items,
            groups_added=comparison.added_translation_groups,
            groups_removed=comparison.removed_translation_groups,
            groups_modified=comparison.modified_translation_groups,
        )

    async def findings(
        self, comparison_id: UUID
    ) -> RevisionFindingChangesResponse:
        comparison = await self._comparison(comparison_id)
        raw_items = comparison.summary_json.get("findingChanges", [])
        items = [
            RevisionFindingChange.model_validate(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        raw_summary = comparison.summary_json.get("findingSummary", {})
        return RevisionFindingChangesResponse(
            comparison_id=comparison.id,
            items=items,
            summary={
                str(key): int(value)
                for key, value in raw_summary.items()
            }
            if isinstance(raw_summary, dict)
            else {},
        )

    async def history(
        self,
        document_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> RevisionComparisonHistoryResponse:
        self._ensure_permission(Permission.REVISION_COMPARISON_VIEW)
        items, total = await self.comparisons.list_by_document(
            document_id,
            department_ids=self._scope_department_ids(),
            page=page,
            page_size=page_size,
        )
        return RevisionComparisonHistoryResponse(
            items=[revision_comparison_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def _comparison(
        self, comparison_id: UUID
    ) -> RevisionComparison:
        self._ensure_permission(Permission.REVISION_COMPARISON_VIEW)
        comparison = await self.comparisons.get_by_id(
            comparison_id,
            department_ids=self._scope_department_ids(),
        )
        if comparison is None:
            raise revision_comparison_not_found()
        return comparison

    @staticmethod
    def _float(value: float | None) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _optional_float(value: object | None) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        return None


def revision_job_response(
    job: RevisionComparisonJob,
) -> RevisionComparisonJobResponse:
    return RevisionComparisonJobResponse(
        id=job.id,
        document_id=job.document_id,
        base_revision_id=job.base_revision_id,
        target_revision_id=job.target_revision_id,
        base_document_file_id=job.base_document_file_id,
        target_document_file_id=job.target_document_file_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        requested_by=job.requested_by,
        requested_at=job.requested_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        cancelled_at=job.cancelled_at,
        error_code=job.error_code,
        error_message=job.error_message,
        result_summary=job.result_summary_json,
    )


def revision_comparison_response(
    item: RevisionComparison,
) -> RevisionComparisonResponse:
    return RevisionComparisonResponse(
        id=item.id,
        revision_comparison_job_id=item.revision_comparison_job_id,
        document_id=item.document_id,
        base_revision_id=item.base_revision_id,
        target_revision_id=item.target_revision_id,
        base_document_file_id=item.base_document_file_id,
        target_document_file_id=item.target_document_file_id,
        base_extraction_run_id=item.base_extraction_run_id,
        target_extraction_run_id=item.target_extraction_run_id,
        base_compliance_run_id=item.base_compliance_run_id,
        target_compliance_run_id=item.target_compliance_run_id,
        base_similarity_run_id=item.base_similarity_run_id,
        target_similarity_run_id=item.target_similarity_run_id,
        base_glossary_run_id=item.base_glossary_run_id,
        target_glossary_run_id=item.target_glossary_run_id,
        status=item.status,
        classification=item.classification,
        base_content_hash=item.base_content_hash,
        target_content_hash=item.target_content_hash,
        total_changes=item.total_changes,
        added_blocks=item.added_blocks,
        removed_blocks=item.removed_blocks,
        modified_blocks=item.modified_blocks,
        moved_blocks=item.moved_blocks,
        unchanged_blocks=item.unchanged_blocks,
        added_sections=item.added_sections,
        removed_sections=item.removed_sections,
        modified_sections=item.modified_sections,
        added_translation_groups=item.added_translation_groups,
        removed_translation_groups=item.removed_translation_groups,
        modified_translation_groups=item.modified_translation_groups,
        compliance_score_change=(
            float(item.compliance_score_change)
            if item.compliance_score_change is not None
            else None
        ),
        similarity_score_change=(
            float(item.similarity_score_change)
            if item.similarity_score_change is not None
            else None
        ),
        new_findings=item.new_findings,
        removed_findings=item.removed_findings,
        repeated_findings=item.repeated_findings,
        severity_change_count=item.severity_change_count,
        language_coverage_change=item.language_coverage_change_json,
        summary=item.summary_json,
        warnings=list(item.warnings_json),
        requested_by=item.requested_by,
        started_at=item.started_at,
        completed_at=item.completed_at,
        created_at=item.created_at,
    )


def revision_change_response(
    item: RevisionChange,
) -> RevisionChangeResponse:
    return RevisionChangeResponse(
        id=item.id,
        revision_comparison_id=item.revision_comparison_id,
        change_type=item.change_type,
        entity_type=item.entity_type,
        base_container_id=item.base_container_id,
        target_container_id=item.target_container_id,
        base_section_id=item.base_section_id,
        target_section_id=item.target_section_id,
        base_translation_group_id=item.base_translation_group_id,
        target_translation_group_id=item.target_translation_group_id,
        base_block_id=item.base_block_id,
        target_block_id=item.target_block_id,
        language_code=item.language_code,
        source_reference_base=item.source_reference_base,
        source_reference_target=item.source_reference_target,
        base_text_snapshot=item.base_text_snapshot,
        target_text_snapshot=item.target_text_snapshot,
        text_similarity=(
            float(item.text_similarity)
            if item.text_similarity is not None
            else None
        ),
        structural_similarity=(
            float(item.structural_similarity)
            if item.structural_similarity is not None
            else None
        ),
        alignment_confidence=(
            float(item.alignment_confidence)
            if item.alignment_confidence is not None
            else None
        ),
        character_change_count=item.character_change_count,
        word_change_count=item.word_change_count,
        metadata=item.metadata_json,
        created_at=item.created_at,
    )
