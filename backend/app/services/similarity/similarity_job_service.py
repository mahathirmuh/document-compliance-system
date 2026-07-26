"""Scoped lifecycle operations for translation-similarity jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    AuditAction,
    Permission,
    has_permission,
)
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.compliance_enums import ComplianceRunStatus
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.similarity_enums import (
    ACTIVE_SIMILARITY_JOB_STATUSES,
    SimilarityJobStatus,
    SimilarityJobType,
    SimilarityRunStatus,
)
from app.models.similarity_job import SimilarityJob
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.similarity_job_repository import (
    SimilarityJobRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.schemas.similarity import (
    SimilarityCancelResponse,
    SimilarityJobListResponse,
    SimilarityJobResponse,
    SimilarityQueuedResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import document_conflict, document_error
from app.utils.datetime import utc_now


class SimilarityJobService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.settings = settings
        self.user = user
        self.metadata = metadata
        self.jobs = SimilarityJobRepository(session)
        self.runs = SimilarityRunRepository(session)
        self.files = DocumentFileRepository(session)
        self.compliance_runs = ComplianceRunRepository(session)
        self.audits = AuditLogRepository(session)

    async def start(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID | None,
        language_detection_run_id: UUID | None,
        force: bool,
    ) -> SimilarityQueuedResponse:
        self._ensure_permission(Permission.SIMILARITY_RUN)
        return await self._queue(
            document_file_id=document_file_id,
            compliance_run_id=compliance_run_id,
            language_detection_run_id=language_detection_run_id,
            force=force,
            job_type=SimilarityJobType.INITIAL_SIMILARITY,
            reason=None,
        )

    async def rerun(
        self,
        run_id: UUID,
        *,
        reason: str,
    ) -> SimilarityQueuedResponse:
        self._ensure_permission(Permission.SIMILARITY_RERUN)
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise document_error(
                "A rerun reason is required.",
                field="reason",
                code="SIMILARITY_RERUN_REASON_REQUIRED",
                title="Similarity rerun could not be queued.",
            )
        previous = await self.runs.get_by_id(
            run_id, department_ids=self._scope_department_ids()
        )
        if previous is None:
            raise similarity_run_not_found()
        response = await self._queue(
            document_file_id=previous.document_file_id,
            compliance_run_id=previous.compliance_run_id,
            language_detection_run_id=(
                previous.language_detection_run_id
            ),
            force=True,
            job_type=SimilarityJobType.REANALYSIS,
            reason=normalized_reason,
        )
        await self._audit(
            AuditAction.RERUN_TRANSLATION_SIMILARITY,
            entity_type="SimilarityJob",
            entity_id=response.id,
            description="Translation similarity rerun queued.",
            values={
                "previousRunId": str(previous.id),
                "reason": normalized_reason[:2000],
            },
        )
        await self.session.commit()
        return response

    async def get(self, job_id: UUID) -> SimilarityJobResponse:
        self._ensure_permission(Permission.SIMILARITY_VIEW)
        job = await self.jobs.get_by_id(
            job_id, department_ids=self._scope_department_ids()
        )
        if job is None:
            raise similarity_job_not_found()
        return similarity_job_response(job)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        document_id: UUID | None,
        revision_id: UUID | None,
        document_file_id: UUID | None,
        compliance_run_id: UUID | None,
        requested_by: UUID | None,
        statuses: Sequence[SimilarityJobStatus] | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> SimilarityJobListResponse:
        self._ensure_permission(Permission.SIMILARITY_VIEW)
        scope = self._scope_department_ids(department_id)
        items, total = await self.jobs.list_page(
            department_ids=scope,
            search=search,
            department_id=department_id if scope is None else None,
            document_id=document_id,
            revision_id=revision_id,
            document_file_id=document_file_id,
            compliance_run_id=compliance_run_id,
            requested_by=requested_by,
            statuses=statuses,
            requested_from=requested_from,
            requested_to=requested_to,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return SimilarityJobListResponse(
            items=[similarity_job_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def cancel(self, job_id: UUID) -> SimilarityCancelResponse:
        if not (
            has_permission(
                self.user.role,
                Permission.SIMILARITY_RUN,
                is_superuser=self.user.is_superuser,
            )
            or has_permission(
                self.user.role,
                Permission.SIMILARITY_RERUN,
                is_superuser=self.user.is_superuser,
            )
        ):
            raise AuthorizationError()
        job = await self.jobs.get_by_id(
            job_id,
            department_ids=self._scope_department_ids(),
            for_update=True,
        )
        if job is None:
            raise similarity_job_not_found()
        if job.status not in ACTIVE_SIMILARITY_JOB_STATUSES:
            raise document_conflict(
                "Only an active similarity job can be cancelled.",
                code="SIMILARITY_JOB_NOT_CANCELLABLE",
                title="Similarity job cannot be cancelled.",
            )
        if job.status is not SimilarityJobStatus.CANCEL_REQUESTED:
            job.status = SimilarityJobStatus.CANCEL_REQUESTED
            job.current_stage = "Cancellation requested"
            await self._audit(
                AuditAction.CANCEL_TRANSLATION_SIMILARITY,
                entity_type="SimilarityJob",
                entity_id=job.id,
                description="Translation similarity cancellation requested.",
                values={"documentFileId": str(job.document_file_id)},
            )
            await self.session.commit()
        return SimilarityCancelResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            current_stage=job.current_stage,
            cancelled_at=job.cancelled_at,
        )

    async def _queue(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID | None,
        language_detection_run_id: UUID | None,
        force: bool,
        job_type: SimilarityJobType,
        reason: str | None,
    ) -> SimilarityQueuedResponse:
        document_file = await self._available_file(document_file_id)
        resolved_compliance_id = (
            compliance_run_id or document_file.latest_compliance_run_id
        )
        compliance = (
            await self.compliance_runs.get_by_id(resolved_compliance_id)
            if resolved_compliance_id is not None
            else None
        )
        if (
            compliance is None
            or compliance.document_file_id != document_file.id
            or compliance.id != document_file.latest_compliance_run_id
            or compliance.status
            not in {
                ComplianceRunStatus.COMPLETED,
                ComplianceRunStatus.PARTIALLY_COMPLETED,
            }
            or not compliance.source_content_hash
        ):
            raise document_error(
                "A latest compatible compliance result is required.",
                field="complianceRunId",
                code="SIMILARITY_COMPLIANCE_RUN_REQUIRED",
                title="Similarity prerequisites are incomplete.",
            )
        resolved_language_id = (
            language_detection_run_id
            or compliance.language_detection_run_id
        )
        if (
            resolved_language_id != compliance.language_detection_run_id
            or resolved_language_id
            != document_file.latest_language_detection_run_id
        ):
            raise document_error(
                "A latest compatible language result is required.",
                field="languageDetectionRunId",
                code="SIMILARITY_LANGUAGE_RESULT_REQUIRED",
                title="Similarity prerequisites are incompatible.",
            )
        active = await self.jobs.get_active(
            document_file.id,
            source_content_hash=compliance.source_content_hash,
        )
        if active is not None:
            raise document_conflict(
                "An equivalent similarity job is already active.",
                code="SIMILARITY_JOB_ALREADY_ACTIVE",
                title="Similarity job is already active.",
            )
        provider = str(
            getattr(
                self.settings,
                "similarity_provider",
                "sentence_transformer",
            )
        )
        model_name = str(
            getattr(
                self.settings,
                "similarity_model_name",
                (
                    "sentence-transformers/"
                    "paraphrase-multilingual-MiniLM-L12-v2"
                ),
            )
        )
        if not force:
            existing = await self.runs.find_equivalent(
                document_file_id=document_file.id,
                compliance_run_id=compliance.id,
                source_content_hash=compliance.source_content_hash,
                provider=provider,
                model_name=model_name,
            )
            if existing is not None:
                return SimilarityQueuedResponse(
                    id=existing.similarity_job_id,
                    status=(
                        SimilarityJobStatus.PARTIALLY_COMPLETED
                        if existing.status
                        is SimilarityRunStatus.PARTIALLY_COMPLETED
                        else SimilarityJobStatus.COMPLETED
                    ),
                    progress=100,
                    document_file_id=document_file.id,
                    run_id=existing.id,
                    reused_existing_result=True,
                )
        maximum_attempts = (
            int(getattr(self.settings, "similarity_max_retries", 1)) + 1
        )
        details = {"rerunReason": reason} if reason else None
        job = SimilarityJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            compliance_run_id=compliance.id,
            language_detection_run_id=resolved_language_id,
            job_type=job_type,
            status=SimilarityJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            source_content_hash=compliance.source_content_hash,
            requested_by=self.user.id,
            maximum_attempts=max(1, maximum_attempts),
            provider=provider,
            model_name=model_name,
            error_details_json=details,
        )
        await self.jobs.add(job)
        await self._audit(
            AuditAction.QUEUE_TRANSLATION_SIMILARITY,
            entity_type="SimilarityJob",
            entity_id=job.id,
            description="Translation similarity job queued.",
            values={
                "documentFileId": str(document_file.id),
                "complianceRunId": str(compliance.id),
                "sourceContentHash": compliance.source_content_hash,
                "jobType": job.job_type.value,
                "provider": provider,
                "modelName": model_name,
            },
        )
        await self.session.commit()
        await self._dispatch(job)
        return SimilarityQueuedResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            document_file_id=document_file.id,
            run_id=None,
            reused_existing_result=False,
        )

    async def _available_file(self, file_id: UUID) -> DocumentFile:
        document_file = await self.files.get_by_id(file_id, for_update=True)
        if document_file is None or not self._can_access_department(
            document_file.document.department_id
        ):
            raise document_error(
                "The document file does not exist or is outside your scope.",
                code="SIMILARITY_SOURCE_NOT_AVAILABLE",
                status_code=HTTPStatus.NOT_FOUND,
                title="Document file was not found.",
            )
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
            or document_file.deleted_at is not None
            or document_file.document.is_archived
        ):
            raise document_error(
                "Only a current available file can be analysed.",
                field="documentFileId",
                code="SIMILARITY_SOURCE_NOT_AVAILABLE",
                title="Similarity source is not available.",
            )
        return document_file

    async def _dispatch(self, job: SimilarityJob) -> None:
        try:
            from app.workers.similarity_tasks import process_similarity_job

            worker_reference = str(uuid4())
            details = dict(job.error_details_json or {})
            details["workerReference"] = worker_reference
            job.error_details_json = details
            await self.session.commit()
            process_similarity_job.apply_async(
                args=[str(job.id)],
                queue=str(
                    getattr(
                        self.settings,
                        "similarity_queue_name",
                        "similarity",
                    )
                ),
                task_id=worker_reference,
            )
        except Exception as exc:
            await self.session.rollback()
            fresh = await self.jobs.get_by_id(job.id, for_update=True)
            if fresh is not None:
                fresh.status = SimilarityJobStatus.FAILED
                fresh.current_stage = "Failed"
                fresh.failed_at = utc_now()
                fresh.error_code = "SIMILARITY_WORKER_UNAVAILABLE"
                fresh.error_message = (
                    "The similarity worker could not accept this job."
                )
                await self._audit(
                    AuditAction.FAIL_TRANSLATION_SIMILARITY,
                    entity_type="SimilarityJob",
                    entity_id=fresh.id,
                    description="Translation similarity dispatch failed.",
                    values={
                        "documentFileId": str(fresh.document_file_id),
                        "errorCode": fresh.error_code,
                    },
                )
                await self.session.commit()
            raise document_error(
                "The similarity worker is temporarily unavailable.",
                code="SIMILARITY_WORKER_UNAVAILABLE",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="Similarity job could not be queued.",
            ) from exc

    async def _audit(
        self,
        action: AuditAction,
        *,
        entity_type: str,
        entity_id: UUID,
        description: str,
        values: dict[str, object],
    ) -> None:
        await self.audits.create(
            user_id=self.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            new_values=values,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
        )

    def _scope_department_ids(
        self,
        requested: UUID | None = None,
    ) -> Sequence[UUID] | None:
        if self._view_all_departments:
            return [requested] if requested is not None else None
        department_id = self.user.department_id
        if department_id is None:
            raise AuthorizationError(
                "A department assignment is required for similarity access."
            )
        if requested is not None and requested != department_id:
            raise AuthorizationError(
                "The requested department is outside your similarity scope."
            )
        return [department_id]

    @property
    def _view_all_departments(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.SIMILARITY_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        )

    def _can_access_department(self, department_id: UUID) -> bool:
        return self._view_all_departments or (
            self.user.department_id == department_id
            and self.user.department_id is not None
        )

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()


def similarity_job_not_found():
    return document_error(
        "Similarity job does not exist or is outside your scope.",
        code="SIMILARITY_JOB_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Similarity job was not found.",
    )


def similarity_run_not_found():
    return document_error(
        "Similarity result does not exist or is outside your scope.",
        code="SIMILARITY_RUN_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Similarity result was not found.",
    )


def similarity_job_response(job: SimilarityJob) -> SimilarityJobResponse:
    document = job.document
    revision = job.revision
    document_file = job.document_file
    requester = job.requester
    return SimilarityJobResponse(
        id=job.id,
        document_id=job.document_id,
        document_revision_id=job.document_revision_id,
        document_file_id=job.document_file_id,
        compliance_run_id=job.compliance_run_id,
        language_detection_run_id=job.language_detection_run_id,
        document={
            "id": document.id,
            "base_document_code": document.base_document_code,
            "title": document.title,
            "department_id": document.department_id,
        },
        revision={
            "id": revision.id,
            "revision_code": revision.revision_code,
            "full_document_code": revision.full_document_code,
        },
        file={
            "id": document_file.id,
            "filename": document_file.original_filename,
            "file_extension": document_file.file_extension,
        },
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        source_content_hash=job.source_content_hash,
        provider=job.provider,
        model_name=job.model_name,
        requested_by=(
            {"id": requester.id, "name": requester.name}
            if requester is not None
            else None
        ),
        requested_at=job.requested_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        cancelled_at=job.cancelled_at,
        attempt_number=job.attempt_number,
        maximum_attempts=job.maximum_attempts,
        error_code=job.error_code,
        error_message=job.error_message,
        error_details=job.error_details_json,
        result_summary=job.result_summary_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
