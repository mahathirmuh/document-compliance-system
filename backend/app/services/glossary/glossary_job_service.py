"""Glossary validation queue, lifecycle, scope, and history service."""

from __future__ import annotations

import builtins
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict, Unpack
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.compliance_enums import ComplianceRunStatus
from app.models.compliance_run import ComplianceRun
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.glossary_enums import (
    ACTIVE_GLOSSARY_VALIDATION_STATUSES,
    GlossaryValidationJobType,
    GlossaryValidationStatus,
)
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.glossary_profile_repository import (
    GlossaryProfileRepository,
)
from app.repositories.glossary_validation_repository import (
    GlossaryValidationRepository,
)
from app.schemas.glossary_validation import (
    GlossaryValidationHistoryResponse,
    GlossaryValidationJobListResponse,
    GlossaryValidationQueuedResponse,
    GlossaryValidationRunResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.base import (
    GlossaryServiceBase,
    glossary_error,
    glossary_not_found,
)
from app.utils.datetime import utc_now

if TYPE_CHECKING:
    from app.core.config import Settings

_USABLE_LANGUAGE_STATUSES = {
    LanguageDetectionRunStatus.COMPLETED,
    LanguageDetectionRunStatus.PARTIALLY_COMPLETED,
}
_USABLE_COMPLIANCE_STATUSES = {
    ComplianceRunStatus.COMPLETED,
    ComplianceRunStatus.PARTIALLY_COMPLETED,
}


class GlossaryJobFilters(TypedDict, total=False):
    document_id: UUID | None
    document_file_id: UUID | None
    status: GlossaryValidationStatus | None
    requested_by: UUID | None
    requested_from: datetime | None
    requested_to: datetime | None
    search: str | None
    sort_order: str


def glossary_run_response(
    run: GlossaryValidationRun,
) -> GlossaryValidationRunResponse:
    return GlossaryValidationRunResponse(
        id=run.id,
        job_id=run.id,
        document_id=run.document_id,
        document_revision_id=run.document_revision_id,
        document_file_id=run.document_file_id,
        compliance_run_id=run.compliance_run_id,
        language_detection_run_id=run.language_detection_run_id,
        glossary_profile_ids=[
            UUID(item) for item in run.glossary_profile_ids_json
        ],
        profile_snapshots=list(run.profile_snapshots_json),
        job_type=run.job_type,
        status=run.status,
        progress=run.progress,
        current_stage=run.current_stage,
        source_content_hash=run.source_content_hash,
        total_terms=run.total_terms,
        matched_terms=run.matched_terms,
        preferred_term_matches=run.preferred_term_matches,
        forbidden_term_matches=run.forbidden_term_matches,
        missing_required_translations=(
            run.missing_required_translations
        ),
        inconsistent_terms=run.inconsistent_terms,
        exception_applied_count=run.exception_applied_count,
        total_findings=run.total_findings,
        metrics=dict(run.metrics_json),
        warnings=run.warnings_json,
        error_code=run.error_code,
        error_message=run.error_message,
        requested_by=run.requested_by,
        requested_at=run.requested_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        failed_at=run.failed_at,
        cancel_requested_at=run.cancel_requested_at,
        cancelled_at=run.cancelled_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


class GlossaryJobService(GlossaryServiceBase):
    """Resolve current retained inputs and queue local glossary validation."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.runs = GlossaryValidationRepository(session)
        self.files = DocumentFileRepository(session)
        self.profiles = GlossaryProfileRepository(session)

    async def start(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID | None,
        profile_ids: list[UUID],
        force: bool,
    ) -> GlossaryValidationQueuedResponse:
        return await self._queue(
            document_file_id=document_file_id,
            compliance_run_id=compliance_run_id,
            profile_ids=profile_ids,
            force=force,
            job_type=(
                GlossaryValidationJobType.MANUAL
                if force
                else GlossaryValidationJobType.INITIAL
            ),
            reason=None,
        )

    async def revalidate(
        self,
        run_id: UUID,
        *,
        reason: str,
        profile_ids: list[UUID],
    ) -> GlossaryValidationQueuedResponse:
        previous = await self.runs.get_by_id(
            run_id,
            department_ids=self.department_ids,
        )
        if previous is None:
            raise glossary_not_found("Glossary validation run")
        return await self._queue(
            document_file_id=previous.document_file_id,
            compliance_run_id=previous.compliance_run_id,
            profile_ids=(
                profile_ids
                or [
                    UUID(item)
                    for item in previous.glossary_profile_ids_json
                ]
            ),
            force=True,
            job_type=GlossaryValidationJobType.REVALIDATION,
            reason=reason,
        )

    async def _queue(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID | None,
        profile_ids: list[UUID],
        force: bool,
        job_type: GlossaryValidationJobType,
        reason: str | None,
    ) -> GlossaryValidationQueuedResponse:
        document_file = await self._available_file(
            document_file_id,
            for_update=True,
        )
        compliance = await self._resolve_compliance_run(
            document_file,
            compliance_run_id,
        )
        language = await self._resolve_language_run(
            document_file,
            compliance,
        )
        profiles = await self._resolve_profiles(
            document_file,
            profile_ids,
        )
        if not profiles:
            raise glossary_error(
                "No active glossary profile applies to this document.",
                field="profileIds",
            )
        active = await self.runs.get_active_for_file(
            document_file.id,
            source_content_hash=language.source_content_hash,
            for_update=True,
        )
        if active is not None:
            raise glossary_error(
                "An active glossary validation already exists for this "
                "source.",
                field="documentFileId",
                status_code=409,
            )
        selected_ids = [profile.id for profile in profiles]
        profile_snapshots = [
            self._profile_snapshot(profile) for profile in profiles
        ]
        if not force:
            existing = await self.runs.get_latest_completed_for_file(
                document_file.id,
                source_content_hash=language.source_content_hash,
                profile_ids=selected_ids,
            )
            if (
                existing is not None
                and existing.profile_snapshots_json == profile_snapshots
            ):
                return GlossaryValidationQueuedResponse(
                    job_id=existing.id,
                    run_id=existing.id,
                    status=existing.status,
                    progress=100,
                    document_file_id=document_file.id,
                    reused_existing_result=True,
                )
        run = GlossaryValidationRun(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            compliance_run_id=(
                compliance.id if compliance is not None else None
            ),
            language_detection_run_id=language.id,
            glossary_profile_ids_json=[
                str(profile.id) for profile in profiles
            ],
            profile_snapshots_json=profile_snapshots,
            job_type=job_type,
            status=GlossaryValidationStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            source_content_hash=language.source_content_hash,
            requested_by=self.user.id,
            requested_at=utc_now(),
            error_details_json=(
                {"revalidationReason": reason.strip()}
                if reason
                else None
            ),
        )
        try:
            await self.runs.add(run)
            await self.audit(
                action=AuditAction.QUEUE_GLOSSARY_VALIDATION,
                entity_type="GlossaryValidationRun",
                entity_id=run.id,
                description="Glossary validation queued.",
                new_values={
                    "documentFileId": str(document_file.id),
                    "complianceRunId": (
                        str(compliance.id)
                        if compliance is not None
                        else None
                    ),
                    "languageDetectionRunId": str(language.id),
                    "profileIds": [
                        str(item) for item in selected_ids
                    ],
                    "sourceContentHash": language.source_content_hash,
                    "jobType": job_type.value,
                    **({"reason": reason.strip()} if reason else {}),
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise glossary_error(
                "An active glossary validation already exists.",
                field="documentFileId",
                status_code=409,
            ) from exc
        await self._dispatch(run.id)
        return GlossaryValidationQueuedResponse(
            job_id=run.id,
            run_id=run.id,
            status=run.status,
            progress=run.progress,
            document_file_id=run.document_file_id,
            reused_existing_result=False,
        )

    async def get(self, run_id: UUID) -> GlossaryValidationRunResponse:
        run = await self.runs.get_by_id(
            run_id,
            department_ids=self.department_ids,
        )
        if run is None:
            raise glossary_not_found("Glossary validation run")
        return glossary_run_response(run)

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        **filters: Unpack[GlossaryJobFilters],
    ) -> GlossaryValidationJobListResponse:
        items, total = await self.runs.list_page(
            department_ids=self.department_ids,
            page=page,
            page_size=page_size,
            **filters,
        )
        return GlossaryValidationJobListResponse(
            items=[glossary_run_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def history(
        self,
        document_file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> GlossaryValidationHistoryResponse:
        document_file = await self._available_file(
            document_file_id,
            for_update=False,
            current_required=False,
        )
        items, total = await self.runs.list_page(
            department_ids=self.department_ids,
            document_file_id=document_file.id,
            page=page,
            page_size=page_size,
        )
        return GlossaryValidationHistoryResponse(
            items=[glossary_run_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def current(
        self,
        document_file_id: UUID,
    ) -> GlossaryValidationRunResponse:
        document_file = await self._available_file(
            document_file_id,
            for_update=False,
            current_required=False,
        )
        run = await self.runs.get_latest_completed_for_file(
            document_file.id
        )
        if run is None:
            raise glossary_not_found("Glossary validation result")
        return glossary_run_response(run)

    async def cancel(
        self,
        run_id: UUID,
    ) -> GlossaryValidationRunResponse:
        run = await self.runs.get_by_id(
            run_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if run is None:
            raise glossary_not_found("Glossary validation run")
        if run.status not in ACTIVE_GLOSSARY_VALIDATION_STATUSES:
            raise glossary_error(
                "Only an active glossary validation can be cancelled.",
                status_code=409,
            )
        if run.status is not GlossaryValidationStatus.CANCEL_REQUESTED:
            run.status = GlossaryValidationStatus.CANCEL_REQUESTED
            run.current_stage = "Cancellation requested"
            run.cancel_requested_at = utc_now()
            await self.audit(
                action=AuditAction.FAIL_GLOSSARY_VALIDATION,
                entity_type="GlossaryValidationRun",
                entity_id=run.id,
                description="Glossary validation cancellation requested.",
                new_values={"status": run.status.value},
            )
            await self.session.commit()
        return glossary_run_response(run)

    async def _available_file(
        self,
        file_id: UUID,
        *,
        for_update: bool,
        current_required: bool = True,
    ) -> DocumentFile:
        item = await self.files.get_by_id(file_id, for_update=for_update)
        if item is None:
            raise glossary_not_found("Document file")
        if (
            self.department_ids is not None
            and item.document.department_id not in self.department_ids
        ):
            raise glossary_not_found("Document file")
        if (
            item.file_status is not DocumentFileStatus.AVAILABLE
            or item.deleted_at is not None
            or item.document.is_archived
            or (current_required and not item.is_current)
        ):
            raise glossary_error(
                "Only a current available file may be validated.",
                field="documentFileId",
            )
        return item

    async def _resolve_compliance_run(
        self,
        document_file: DocumentFile,
        run_id: UUID | None,
    ) -> ComplianceRun | None:
        selected_id = run_id or document_file.latest_compliance_run_id
        if selected_id is None:
            return None
        run = await self.session.get(ComplianceRun, selected_id)
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.status not in _USABLE_COMPLIANCE_STATUSES
        ):
            raise glossary_error(
                "A compatible completed compliance run is required.",
                field="complianceRunId",
            )
        return run

    async def _resolve_language_run(
        self,
        document_file: DocumentFile,
        compliance: ComplianceRun | None,
    ) -> LanguageDetectionRun:
        selected_id = (
            compliance.language_detection_run_id
            if compliance is not None
            else document_file.latest_language_detection_run_id
        )
        run = (
            await self.session.get(LanguageDetectionRun, selected_id)
            if selected_id is not None
            else None
        )
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.id != document_file.latest_language_detection_run_id
            or run.status not in _USABLE_LANGUAGE_STATUSES
            or not run.source_content_hash
        ):
            raise glossary_error(
                "A latest completed language detection run is required.",
                field="documentFileId",
            )
        return run

    async def _resolve_profiles(
        self,
        document_file: DocumentFile,
        profile_ids: builtins.list[UUID],
    ) -> builtins.list[GlossaryProfile]:
        if profile_ids:
            profiles = await self.profiles.list_by_ids(
                profile_ids,
                department_ids=self.department_ids,
            )
            if len(profiles) != len(profile_ids):
                raise glossary_error(
                    "One or more glossary profiles were not found.",
                    field="profileIds",
                )
            return profiles
        return await self.profiles.resolve_for_scope(
            department_id=document_file.document.department_id,
            document_type_id=document_file.document.document_type_id,
        )

    @staticmethod
    def _profile_snapshot(profile: GlossaryProfile) -> dict[str, object]:
        return {
            "id": str(profile.id),
            "code": profile.code,
            "name": profile.name,
            "scopeType": profile.scope_type.value,
            "departmentId": (
                str(profile.department_id)
                if profile.department_id is not None
                else None
            ),
            "documentTypeId": (
                str(profile.document_type_id)
                if profile.document_type_id is not None
                else None
            ),
            "version": profile.version,
            "terms": [
                {
                    "id": str(term.id),
                    "termCode": term.term_code,
                    "conceptName": term.concept_name,
                    "termType": term.term_type.value,
                    "severity": term.severity.value,
                    "isCaseSensitive": term.is_case_sensitive,
                    "matchWholeWord": term.match_whole_word,
                    "allowInflection": term.allow_inflection,
                    "isRegex": term.is_regex,
                    "translations": [
                        {
                            "id": str(translation.id),
                            "languageCode": (
                                translation.language_code.value
                            ),
                            "termText": translation.term_text,
                            "normalisedTerm": (
                                translation.normalised_term
                            ),
                            "isPreferred": translation.is_preferred,
                            "isForbidden": translation.is_forbidden,
                            "isRequired": translation.is_required,
                            "priority": translation.priority,
                            "variants": [
                                {
                                    "id": str(variant.id),
                                    "variantText": variant.variant_text,
                                    "normalisedVariant": (
                                        variant.normalised_variant
                                    ),
                                    "variantType": (
                                        variant.variant_type.value
                                    ),
                                    "isAllowed": variant.is_allowed,
                                }
                                for variant in translation.variants
                                if variant.is_active
                            ],
                        }
                        for translation in term.translations
                        if translation.is_active
                    ],
                }
                for term in profile.terms
                if term.is_active
            ],
        }

    async def _dispatch(self, run_id: UUID) -> None:
        from app.workers.glossary_tasks import (
            process_glossary_validation_job,
        )

        try:
            process_glossary_validation_job.apply_async(
                args=[str(run_id)],
                queue=getattr(
                    self.settings,
                    "glossary_queue_name",
                    "glossary",
                ),
            )
        except Exception as exc:
            async with self.session.begin():
                run = await self.runs.get_by_id(run_id, for_update=True)
                if run is not None and run.status in (
                    ACTIVE_GLOSSARY_VALIDATION_STATUSES
                ):
                    run.status = GlossaryValidationStatus.FAILED
                    run.progress = 0
                    run.current_stage = "Queue dispatch failed"
                    run.error_code = "GLOSSARY_QUEUE_UNAVAILABLE"
                    run.error_message = (
                        "Glossary validation could not be dispatched."
                    )
                    run.failed_at = utc_now()
                    await self.audit(
                        action=AuditAction.FAIL_GLOSSARY_VALIDATION,
                        entity_type="GlossaryValidationRun",
                        entity_id=run.id,
                        description="Glossary validation dispatch failed.",
                        new_values={"errorCode": run.error_code},
                    )
            raise glossary_error(
                "Glossary worker queue is unavailable.",
                status_code=503,
            ) from exc
