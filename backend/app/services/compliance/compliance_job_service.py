"""User-facing Phase 8 compliance queue and job lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.compliance_enums import (
    ACTIVE_COMPLIANCE_JOB_STATUSES,
    ComplianceJobStatus,
    ComplianceJobType,
    ComplianceStatus,
)
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extraction_run import ExtractionRun, ExtractionRunStatus
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.models.user import User
from app.models.validation_rule import ValidationRule
from app.repositories.compliance_job_repository import (
    ComplianceJobRepository,
)
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.compliance import (
    ComplianceCancelResponse,
    ComplianceDocumentReference,
    ComplianceFileReference,
    ComplianceJobListResponse,
    ComplianceJobResponse,
    ComplianceQueuedResponse,
    ComplianceRequesterReference,
    ComplianceRevisionReference,
    ComplianceRuleReference,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_context_service import (
    ComplianceContextBuildError,
    ComplianceContextService,
)
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
)
from app.utils.datetime import utc_now

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


def compliance_job_not_found() -> Exception:
    return document_error(
        "The compliance job does not exist or is outside your scope.",
        code="COMPLIANCE_JOB_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Compliance job was not found.",
    )


def compliance_run_not_found() -> Exception:
    return document_error(
        "The compliance run does not exist or is outside your scope.",
        code="COMPLIANCE_RESULT_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Compliance run was not found.",
    )


class ComplianceJobService(DocumentServiceBase):
    """Resolve retained prerequisites, queue work, and expose job state."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.jobs = ComplianceJobRepository(session)
        self.runs = ComplianceRunRepository(session)
        self.files = DocumentFileRepository(session)
        self.extractions = ExtractionRunRepository(session)
        self.ocr_runs = OCRRunRepository(session)
        self.language_runs = LanguageDetectionRunRepository(session)
        self.rules = ValidationRuleRepository(session)
        self.contexts = ComplianceContextService(
            maximum_blocks=settings.compliance_max_blocks
        )

    async def start(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID | None,
        ocr_run_id: UUID | None,
        language_detection_run_id: UUID | None,
        validation_rule_id: UUID | None,
        force: bool,
    ) -> ComplianceQueuedResponse:
        self._ensure_permission(
            Permission.COMPLIANCE_REVALIDATE
            if force
            else Permission.COMPLIANCE_VALIDATE
        )
        return await self._queue(
            document_file_id=document_file_id,
            extraction_run_id=extraction_run_id,
            ocr_run_id=ocr_run_id,
            language_detection_run_id=language_detection_run_id,
            validation_rule_id=validation_rule_id,
            force=force,
            job_type=(
                ComplianceJobType.MANUAL_VALIDATION
                if force
                else ComplianceJobType.INITIAL_VALIDATION
            ),
            reason=None,
        )

    async def revalidate(
        self,
        run_id: UUID,
        *,
        reason: str,
        validation_rule_id: UUID | None,
    ) -> ComplianceQueuedResponse:
        self._ensure_permission(Permission.COMPLIANCE_REVALIDATE)
        run = await self.runs.get_by_id(
            run_id,
            department_ids=self._scope_department_ids(),
        )
        if run is None:
            raise compliance_run_not_found()
        response = await self._queue(
            document_file_id=run.document_file_id,
            extraction_run_id=None,
            ocr_run_id=None,
            language_detection_run_id=None,
            validation_rule_id=validation_rule_id or run.validation_rule_id,
            force=True,
            job_type=ComplianceJobType.REVALIDATION,
            reason=reason,
        )
        return response

    async def _queue(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID | None,
        ocr_run_id: UUID | None,
        language_detection_run_id: UUID | None,
        validation_rule_id: UUID | None,
        force: bool,
        job_type: ComplianceJobType,
        reason: str | None,
    ) -> ComplianceQueuedResponse:
        if job_type is ComplianceJobType.REVALIDATION and not (reason or "").strip():
            raise document_error(
                "A reason is required for compliance revalidation.",
                field="reason",
                code="COMPLIANCE_REVALIDATION_REASON_REQUIRED",
                title="Compliance revalidation reason is required.",
            )
        document_file = await self._available_file(
            document_file_id,
            for_update=True,
        )
        extraction = await self._resolve_extraction(
            document_file,
            extraction_run_id,
        )
        language = await self._resolve_language_run(
            document_file,
            extraction,
            language_detection_run_id,
        )
        ocr = await self._resolve_ocr(
            document_file,
            extraction,
            language,
            ocr_run_id,
        )
        rule = await self._resolve_rule(document_file, validation_rule_id)
        source_hash = language.source_content_hash

        active = await self.jobs.get_active(
            document_file.id,
            for_update=True,
        )
        if active is not None:
            raise document_conflict(
                "An active compliance validation already exists for this file.",
                field="documentFileId",
                code="COMPLIANCE_ACTIVE_JOB_EXISTS",
                title="Active compliance validation already exists.",
            )

        if not force:
            equivalent = await self.runs.find_equivalent(
                document_file_id=document_file.id,
                source_content_hash=source_hash,
                validation_rule_id=rule.id,
            )
            if equivalent is not None and self._same_rule_snapshot(
                equivalent,
                rule,
            ):
                return ComplianceQueuedResponse(
                    job_id=equivalent.compliance_job_id,
                    status=(
                        ComplianceJobStatus.PARTIALLY_COMPLETED
                        if equivalent.status.value == "PARTIALLY_COMPLETED"
                        else ComplianceJobStatus.COMPLETED
                    ),
                    progress=100,
                    document_file_id=document_file.id,
                    run_id=equivalent.id,
                    reused_existing_result=True,
                )

        job = ComplianceJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            extraction_run_id=extraction.id,
            ocr_run_id=ocr.id if ocr is not None else None,
            language_detection_run_id=language.id,
            validation_rule_id=rule.id,
            job_type=job_type,
            status=ComplianceJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            source_content_hash=source_hash,
            requested_by=self.user.id,
            requested_at=utc_now(),
            attempt_number=1,
            maximum_attempts=self.settings.compliance_max_retries + 1,
            error_details_json=(
                {
                    "revalidationReason": reason.strip(),
                }
                if reason
                else None
            ),
        )
        try:
            await self.jobs.add(job)
            await self.audit(
                action=(
                    AuditAction.REVALIDATE_COMPLIANCE
                    if job_type is ComplianceJobType.REVALIDATION
                    else AuditAction.QUEUE_COMPLIANCE_VALIDATION
                ),
                entity_type="ComplianceJob",
                entity_id=job.id,
                description=(
                    "Compliance revalidation queued."
                    if job_type is ComplianceJobType.REVALIDATION
                    else "Compliance validation queued."
                ),
                new_values={
                    "documentFileId": str(document_file.id),
                    "extractionRunId": str(extraction.id),
                    "ocrRunId": str(ocr.id) if ocr is not None else None,
                    "languageDetectionRunId": str(language.id),
                    "validationRuleId": str(rule.id),
                    "sourceContentHash": source_hash,
                    "jobType": job_type.value,
                    **({"reason": reason.strip()} if reason else {}),
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "An active compliance validation already exists for this source.",
                field="documentFileId",
                code="COMPLIANCE_ACTIVE_JOB_EXISTS",
                title="Active compliance validation already exists.",
            ) from exc

        await self._dispatch(job)
        return ComplianceQueuedResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            document_file_id=document_file.id,
            run_id=None,
            reused_existing_result=False,
        )

    async def get(self, job_id: UUID) -> ComplianceJobResponse:
        self._ensure_permission(Permission.COMPLIANCE_VIEW)
        job = await self.jobs.get_by_id(
            job_id,
            department_ids=self._scope_department_ids(),
        )
        if job is None:
            raise compliance_job_not_found()
        return compliance_job_response(job)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        document_id: UUID | None,
        revision_id: UUID | None,
        document_file_id: UUID | None,
        validation_rule_id: UUID | None,
        compliance_status: ComplianceStatus | None,
        requested_by: UUID | None,
        statuses: Sequence[ComplianceJobStatus] | None,
        requested_from: datetime | None,
        requested_to: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> ComplianceJobListResponse:
        self._ensure_permission(Permission.COMPLIANCE_VIEW)
        scope = self._scope_department_ids(department_id)
        items, total = await self.jobs.list_page(
            department_ids=scope,
            search=search,
            document_id=document_id,
            revision_id=revision_id,
            document_file_id=document_file_id,
            validation_rule_id=validation_rule_id,
            compliance_status=compliance_status,
            requested_by=requested_by,
            statuses=statuses,
            requested_from=requested_from,
            requested_to=requested_to,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return ComplianceJobListResponse(
            items=[compliance_job_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def cancel(self, job_id: UUID) -> ComplianceCancelResponse:
        if not any(
            has_permission(
                self.user.role,
                permission,
                is_superuser=self.user.is_superuser,
            )
            for permission in (
                Permission.COMPLIANCE_VALIDATE,
                Permission.COMPLIANCE_REVALIDATE,
            )
        ):
            raise AuthorizationError()
        job = await self.jobs.get_by_id(
            job_id,
            department_ids=self._scope_department_ids(),
            for_update=True,
        )
        if job is None:
            raise compliance_job_not_found()
        if job.status not in ACTIVE_COMPLIANCE_JOB_STATUSES:
            raise document_conflict(
                "Only an active compliance job can be cancelled.",
                code="COMPLIANCE_JOB_NOT_CANCELLABLE",
                title="Compliance validation cannot be cancelled.",
            )
        if job.status is not ComplianceJobStatus.CANCEL_REQUESTED:
            job.status = ComplianceJobStatus.CANCEL_REQUESTED
            job.current_stage = "Cancellation requested"
            await self.audit(
                action=AuditAction.CANCEL_COMPLIANCE_VALIDATION,
                entity_type="ComplianceJob",
                entity_id=job.id,
                description="Compliance validation cancellation requested.",
                new_values={
                    "documentFileId": str(job.document_file_id),
                    "status": job.status.value,
                },
            )
            await self.session.commit()
        return ComplianceCancelResponse(
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
            raise document_error(
                "The document file does not exist or is outside your scope.",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                status_code=HTTPStatus.NOT_FOUND,
                title="Document file was not found.",
            )
        if not self._can_access_department(document_file.document.department_id):
            raise document_error(
                "The document file does not exist or is outside your scope.",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
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
                "Only a current available file may be validated.",
                field="documentFileId",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                title="Compliance source is not available.",
            )
        return document_file

    async def _resolve_extraction(
        self,
        document_file: DocumentFile,
        run_id: UUID | None,
    ) -> ExtractionRun:
        resolved_id = run_id or document_file.latest_extraction_run_id
        run = (
            await self.extractions.get_by_id(resolved_id)
            if resolved_id is not None
            else None
        )
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.id != document_file.latest_extraction_run_id
            or run.status not in _USABLE_EXTRACTION_STATUSES
        ):
            raise document_error(
                "A latest completed extraction run is required.",
                field="extractionRunId",
                code="COMPLIANCE_EXTRACTION_REQUIRED",
                title="Compliance prerequisites are incomplete.",
            )
        return run

    async def _resolve_language_run(
        self,
        document_file: DocumentFile,
        extraction: ExtractionRun,
        run_id: UUID | None,
    ) -> LanguageDetectionRun:
        resolved_id = run_id or document_file.latest_language_detection_run_id
        run = (
            await self.language_runs.get_by_id(resolved_id)
            if resolved_id is not None
            else None
        )
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.id != document_file.latest_language_detection_run_id
            or run.extraction_run_id != extraction.id
            or run.status not in _USABLE_LANGUAGE_STATUSES
            or not run.source_content_hash
        ):
            raise document_error(
                "A latest compatible language detection run is required.",
                field="languageDetectionRunId",
                code="COMPLIANCE_LANGUAGE_DETECTION_REQUIRED",
                title="Compliance prerequisites are incomplete.",
            )
        return run

    async def _resolve_ocr(
        self,
        document_file: DocumentFile,
        extraction: ExtractionRun,
        language: LanguageDetectionRun,
        run_id: UUID | None,
    ) -> OCRRun | None:
        resolved_id = run_id if run_id is not None else language.ocr_run_id
        run = (
            await self.ocr_runs.get_by_id(resolved_id)
            if resolved_id is not None
            else None
        )
        if extraction.requires_ocr and run is None:
            raise document_error(
                "A latest compatible OCR run is required.",
                field="ocrRunId",
                code="COMPLIANCE_OCR_REQUIRED",
                title="Compliance prerequisites are incomplete.",
            )
        if run is not None and (
            run.document_file_id != document_file.id
            or run.id != document_file.latest_ocr_run_id
            or run.source_extraction_run_id != extraction.id
            or run.id != language.ocr_run_id
            or run.status not in _USABLE_OCR_STATUSES
        ):
            raise document_error(
                "The selected OCR run is not a compatible current source.",
                field="ocrRunId",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                title="Compliance prerequisites are incompatible.",
            )
        if run is None and language.ocr_run_id is not None:
            raise document_error(
                "The language result requires a compatible OCR source.",
                field="ocrRunId",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                title="Compliance prerequisites are incompatible.",
            )
        return run

    async def _resolve_rule(
        self,
        document_file: DocumentFile,
        rule_id: UUID | None,
    ) -> ValidationRule:
        selected_id = rule_id or document_file.revision.validation_rule_id
        rule = (
            await self.rules.get_by_id(selected_id)
            if selected_id is not None
            else await self.rules.get_default(document_file.document.document_type_id)
        )
        if rule is None and selected_id is None:
            rule = await self.rules.get_default(None)
        if (
            rule is None
            or not rule.is_active
            or rule.document_type_id
            not in (None, document_file.document.document_type_id)
        ):
            raise document_error(
                "An active validation rule for this document type is required.",
                field="validationRuleId",
                code="COMPLIANCE_RULE_NOT_FOUND",
                title="Compliance validation rule is not available.",
            )
        try:
            self._rule_snapshot(rule)
        except ComplianceContextBuildError as exc:
            raise document_error(
                str(exc),
                field="validationRuleId",
                code="COMPLIANCE_RULE_INVALID",
                title="Compliance validation rule is invalid.",
            ) from exc
        return rule

    def _same_rule_snapshot(
        self,
        run: ComplianceRun,
        rule: ValidationRule,
    ) -> bool:
        current = self._rule_snapshot(rule).model_dump(
            mode="json",
            by_alias=True,
        )
        return run.rule_snapshot_json == current

    def _rule_snapshot(self, rule: ValidationRule):
        snapshot = self.contexts.snapshot_rule(rule)
        options = dict(snapshot.validation_options)
        options.setdefault(
            "translation_group_min_confidence",
            self.settings.translation_group_min_confidence,
        )
        return snapshot.model_copy(
            update={"validation_options": options},
            deep=True,
        )

    async def _dispatch(self, job: ComplianceJob) -> None:
        try:
            from app.workers.compliance_tasks import process_compliance_job

            worker_reference = str(uuid4())
            details = dict(job.error_details_json or {})
            details["workerReference"] = worker_reference
            job.error_details_json = details
            await self.session.commit()
            process_compliance_job.apply_async(
                args=[str(job.id)],
                queue=self.settings.compliance_queue_name,
                task_id=worker_reference,
            )
        except Exception as exc:
            await self.session.rollback()
            fresh = await self.jobs.get_by_id(job.id, for_update=True)
            if fresh is not None:
                fresh.status = ComplianceJobStatus.FAILED
                fresh.current_stage = "Failed"
                fresh.failed_at = utc_now()
                fresh.error_code = "COMPLIANCE_WORKER_UNAVAILABLE"
                fresh.error_message = "The compliance worker could not accept this job."
                await self.audit(
                    action=AuditAction.FAIL_COMPLIANCE_VALIDATION,
                    entity_type="ComplianceJob",
                    entity_id=fresh.id,
                    description="Compliance validation dispatch failed.",
                    new_values={
                        "documentFileId": str(fresh.document_file_id),
                        "errorCode": fresh.error_code,
                    },
                )
                await self.session.commit()
            raise document_error(
                "The compliance worker is temporarily unavailable.",
                code="COMPLIANCE_WORKER_UNAVAILABLE",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                title="Compliance validation could not be queued.",
            ) from exc

    def _scope_department_ids(
        self,
        requested: UUID | None = None,
    ) -> Sequence[UUID] | None:
        if self._view_all_departments:
            return [requested] if requested is not None else None
        department_id = self.user.department_id
        if department_id is None:
            raise AuthorizationError(
                "A department assignment is required for compliance access."
            )
        if requested is not None and requested != department_id:
            raise AuthorizationError(
                "The requested department is outside your compliance scope."
            )
        return [department_id]

    @property
    def _view_all_departments(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        )

    def _can_access_department(self, department_id: UUID) -> bool:
        return self._view_all_departments or (
            self.user.department_id is not None
            and self.user.department_id == department_id
        )

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()


def compliance_job_response(job: ComplianceJob) -> ComplianceJobResponse:
    """Map one eagerly loaded model to the stable public contract."""

    result = dict(job.result_summary_json or {})
    if result and "totalFindings" not in result:
        result["totalFindings"] = int(result.pop("findings", 0) or 0)
    result.setdefault("runId", None)
    result.setdefault("complianceStatus", None)
    result.setdefault("complianceScore", None)
    result.setdefault("totalFindings", 0)
    result.setdefault("criticalFindings", 0)
    result.setdefault("majorFindings", 0)
    result.setdefault("minorFindings", 0)
    document = job.document
    revision = job.revision
    document_file = job.document_file
    rule = job.validation_rule
    requester = job.requester
    return ComplianceJobResponse(
        id=job.id,
        document_id=job.document_id,
        document_revision_id=job.document_revision_id,
        document_file_id=job.document_file_id,
        extraction_run_id=job.extraction_run_id,
        ocr_run_id=job.ocr_run_id,
        language_detection_run_id=job.language_detection_run_id,
        validation_rule_id=job.validation_rule_id,
        document=ComplianceDocumentReference(
            id=document.id,
            base_document_code=document.base_document_code,
            title=document.title,
            department_id=document.department_id,
        ),
        revision=ComplianceRevisionReference(
            id=revision.id,
            revision_code=revision.revision_code,
            full_document_code=revision.full_document_code,
        ),
        file=ComplianceFileReference(
            id=document_file.id,
            filename=document_file.original_filename,
            file_extension=document_file.file_extension,
        ),
        validation_rule=ComplianceRuleReference(
            id=rule.id,
            code=rule.code,
            name=rule.name,
        ),
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        source_content_hash=job.source_content_hash,
        requested_by=(
            ComplianceRequesterReference(id=requester.id, name=requester.name)
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
        result_summary=result if job.result_summary_json else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
