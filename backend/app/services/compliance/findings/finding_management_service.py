"""Department-scoped persistence and workflow actions for findings."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from datetime import date
from enum import Enum
from http import HTTPStatus
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, case, desc, func, inspect, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.authorization import (
    AuditAction,
    Permission,
    has_permission,
)
from app.core.exceptions import AuthorizationError
from app.models.audit_log import AuditLog
from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.compliance_run import ComplianceRun
from app.models.detected_section import DetectedSection
from app.models.document import Document
from app.models.document_file import DocumentFileStatus
from app.models.finding_occurrence import FindingOccurrence
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.repositories.user import UserRepository
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.schemas.compliance import (
    ComplianceDocumentReference,
    ComplianceRevisionReference,
    ComplianceRuleReference,
)
from app.schemas.document_revision import UserReference
from app.schemas.finding import (
    FindingBulkActionResponse,
    FindingCreateManualRequest,
    FindingFilter,
    FindingHistoryEntry,
    FindingListItem,
    FindingListResponse,
    FindingOccurrenceResponse,
    FindingResponse,
    FindingUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance._compat import json_safe
from app.services.compliance.compliance_export_service import (
    safe_source_reference,
)
from app.services.compliance.findings.finding_resolution_service import (
    FindingResolutionService,
    FindingTransitionError,
)
from app.services.documents.base import DocumentServiceBase, document_error
from app.utils.datetime import utc_now

_EDITABLE_REQUIRED_FIELDS = frozenset(
    {"severity", "title", "description"},
)
_LIVE_MANUAL_SOURCE_STATUSES = frozenset(
    {
        DocumentFileStatus.AVAILABLE,
        DocumentFileStatus.REPLACED,
    }
)
_SORT_FIELDS = {
    "createdAt": ValidationFinding.created_at,
    "created_at": ValidationFinding.created_at,
    "findingCode": ValidationFinding.finding_code,
    "finding_code": ValidationFinding.finding_code,
    "status": ValidationFinding.status,
    "title": ValidationFinding.title,
    "updatedAt": ValidationFinding.updated_at,
    "updated_at": ValidationFinding.updated_at,
}
_MAX_FINDING_HISTORY_ITEMS = 500
_OPEN_FINDING_STATUSES = (
    FindingStatus.OPEN,
    FindingStatus.IN_REVIEW,
    FindingStatus.REOPENED,
)


class FindingManagementService(DocumentServiceBase):
    """Apply finding policy independently of the HTTP boundary."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)
        self.files = DocumentFileRepository(session)
        self.findings = ValidationFindingRepository(session)
        self.users = UserRepository(session)
        self.resolution = FindingResolutionService()

    async def list(
        self,
        filters: FindingFilter,
    ) -> FindingListResponse:
        """Return one filtered page inside the caller's department scope."""

        self._ensure_permission(Permission.FINDINGS_VIEW)
        self._validate_filter_window(filters)
        department_ids = self._scope_department_ids(filters.department_id)
        predicates = self._filter_predicates(
            filters,
            department_ids=department_ids,
        )
        total = int(
            (
                await self.session.scalar(
                    select(func.count(ValidationFinding.id))
                    .join(
                        Document,
                        Document.id == ValidationFinding.document_id,
                    )
                    .where(*predicates)
                )
            )
            or 0
        )
        statement = (
            select(ValidationFinding)
            .join(
                Document,
                Document.id == ValidationFinding.document_id,
            )
            .options(*self._response_options())
            .where(*predicates)
        )
        statement = self._apply_sort(
            statement,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        statement = statement.offset((filters.page - 1) * filters.page_size).limit(
            filters.page_size
        )
        rows = list((await self.session.scalars(statement)).unique().all())
        return FindingListResponse(
            items=[finding_list_item(row) for row in rows],
            page=filters.page,
            pageSize=filters.page_size,
            totalItems=total,
            totalPages=ceil(total / filters.page_size) if total else 0,
        )

    async def get(self, finding_id: UUID) -> FindingResponse:
        self._ensure_permission(Permission.FINDINGS_VIEW)
        finding = await self._scoped_finding(finding_id)
        return await self._detail_response(finding)

    async def create_manual(
        self,
        payload: FindingCreateManualRequest,
    ) -> FindingResponse:
        """Create a user-owned finding that revalidation never manages."""

        self._ensure_permission(Permission.FINDINGS_CREATE_MANUAL)
        document = await self.documents.get_by_id(payload.document_id)
        if document is None or not self._can_access_department(document.department_id):
            raise finding_not_found(
                "The source document does not exist or is outside your scope.",
                code="FINDING_DOCUMENT_NOT_FOUND",
            )
        revision = await self.revisions.get_by_id(
            payload.document_revision_id,
            document_id=document.id,
        )
        if revision is None:
            raise document_error(
                "The revision does not belong to the selected document.",
                field="documentRevisionId",
                code="FINDING_REVISION_MISMATCH",
                title="Manual finding source is invalid.",
            )
        document_file = await self.files.get_by_id(payload.document_file_id)
        if (
            document_file is None
            or document_file.document_id != document.id
            or document_file.document_revision_id != revision.id
            or document_file.file_status not in _LIVE_MANUAL_SOURCE_STATUSES
            or document_file.deleted_at is not None
        ):
            raise document_error(
                "The file does not belong to the selected live revision.",
                field="documentFileId",
                code="FINDING_FILE_MISMATCH",
                title="Manual finding source is invalid.",
            )

        finding = ValidationFinding(
            compliance_run_id=None,
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            validation_rule_id=revision.validation_rule_id,
            finding_code=FindingCode.MANUAL_FINDING,
            finding_type=FindingType.MANUAL,
            severity=payload.severity,
            status=FindingStatus.OPEN,
            title=payload.title,
            description=payload.description,
            recommendation=payload.recommendation,
            page_number=payload.page_number,
            worksheet_name=payload.worksheet_name,
            cell_coordinate=payload.cell_coordinate,
            source_reference=payload.source_reference,
            location_json=dict(payload.location),
            language_code=payload.language_code,
            metrics_json={},
            is_system_generated=False,
            is_repeat=False,
            created_by=self.user.id,
        )
        try:
            await self.findings.add(finding)
            await self.audit(
                action=AuditAction.CREATE_MANUAL_FINDING,
                entity_type="ValidationFinding",
                entity_id=finding.id,
                description="Manual compliance finding created.",
                new_values={
                    "documentId": str(document.id),
                    "documentRevisionId": str(revision.id),
                    "documentFileId": str(document_file.id),
                    "findingCode": FindingCode.MANUAL_FINDING.value,
                    "severity": finding.severity.value,
                    "status": finding.status.value,
                    "isSystemGenerated": False,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._detail_response(await self._scoped_finding(finding.id))

    async def update(
        self,
        finding_id: UUID,
        payload: FindingUpdateRequest,
    ) -> FindingResponse:
        self._ensure_permission(Permission.FINDINGS_UPDATE)
        values = payload.model_dump(exclude_unset=True)
        if not values:
            raise document_error(
                "At least one editable finding field is required.",
                code="FINDING_UPDATE_EMPTY",
                title="Finding update is invalid.",
            )
        null_required = sorted(
            field
            for field in _EDITABLE_REQUIRED_FIELDS
            if field in values and values[field] is None
        )
        if null_required:
            raise document_error(
                f"{null_required[0]} must not be null.",
                field=_camel(null_required[0]),
                code="FINDING_UPDATE_NULL_REQUIRED",
                title="Finding update is invalid.",
            )

        finding = await self._scoped_finding(
            finding_id,
            for_update=True,
        )
        old_values = {
            "status": finding.status.value,
            **{field: _audit_value(getattr(finding, field)) for field in values},
        }
        for field, value in values.items():
            setattr(finding, field, value)
        try:
            await self.session.flush()
            await self.audit(
                action=AuditAction.UPDATE_FINDING,
                entity_type="ValidationFinding",
                entity_id=finding.id,
                description="Compliance finding updated.",
                old_values=old_values,
                new_values={
                    "status": finding.status.value,
                    **{
                        field: _audit_value(getattr(finding, field)) for field in values
                    },
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._detail_response(await self._scoped_finding(finding.id))

    async def review(
        self,
        finding_id: UUID,
        *,
        comment: str,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_REVIEW,
            target=FindingStatus.IN_REVIEW,
            action=AuditAction.REVIEW_FINDING,
            comment=comment,
        )

    async def return_to_open(
        self,
        finding_id: UUID,
        *,
        comment: str,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_REVIEW,
            target=FindingStatus.OPEN,
            action=AuditAction.REVIEW_FINDING,
            comment=comment,
        )

    async def resolve(
        self,
        finding_id: UUID,
        *,
        comment: str,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_RESOLVE,
            target=FindingStatus.RESOLVED,
            action=AuditAction.RESOLVE_FINDING,
            comment=comment,
        )

    async def reopen(
        self,
        finding_id: UUID,
        *,
        reason: str,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_REOPEN,
            target=FindingStatus.REOPENED,
            action=AuditAction.REOPEN_FINDING,
            reason=reason,
        )

    async def mark_false_positive(
        self,
        finding_id: UUID,
        *,
        reason: str,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_FALSE_POSITIVE,
            target=FindingStatus.FALSE_POSITIVE,
            action=AuditAction.MARK_FINDING_FALSE_POSITIVE,
            reason=reason,
        )

    async def accept_risk(
        self,
        finding_id: UUID,
        *,
        reason: str,
        expiry_date: date,
    ) -> FindingResponse:
        return await self._transition(
            finding_id,
            permission=Permission.FINDINGS_RESOLVE,
            target=FindingStatus.ACCEPTED_RISK,
            action=AuditAction.ACCEPT_FINDING_RISK,
            reason=reason,
            expiry_date=expiry_date,
        )

    async def assign(
        self,
        finding_id: UUID,
        *,
        assigned_to: UUID,
    ) -> FindingResponse:
        self._ensure_permission(Permission.FINDINGS_UPDATE)
        finding = await self._scoped_finding(
            finding_id,
            for_update=True,
        )
        target = await self._active_assignment_target(assigned_to)
        self._validate_assignment_department(
            target,
            finding.document.department_id,
        )
        try:
            self.resolution.assign(
                {"status": finding.status.value},
                assigned_to=assigned_to,
            )
        except FindingTransitionError as exc:
            raise transition_error(exc) from exc
        previous = finding.assigned_to
        finding.assigned_to = target.id
        try:
            await self.session.flush()
            await self.audit(
                action=AuditAction.ASSIGN_FINDING,
                entity_type="ValidationFinding",
                entity_id=finding.id,
                description="Compliance finding assigned.",
                old_values={
                    "status": finding.status.value,
                    "assignedTo": (str(previous) if previous is not None else None),
                },
                new_values={
                    "status": finding.status.value,
                    "assignedTo": str(target.id),
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._detail_response(await self._scoped_finding(finding.id))

    async def bulk_assign(
        self,
        finding_ids: Sequence[UUID],
        *,
        assigned_to: UUID,
        maximum_items: int,
    ) -> FindingBulkActionResponse:
        """Assign a bounded finding set only after validating every row."""

        self._ensure_permission(Permission.FINDINGS_UPDATE)
        normalized_ids = self._bounded_bulk_ids(
            finding_ids,
            maximum_items=maximum_items,
        )
        try:
            target = await self._active_assignment_target(assigned_to)
            scoped_findings = await self._scoped_findings_for_update(normalized_ids)
            for finding, department_id in scoped_findings:
                self._validate_assignment_department(target, department_id)
                try:
                    self.resolution.assign(
                        {"status": finding.status.value},
                        assigned_to=target.id,
                    )
                except FindingTransitionError as exc:
                    raise transition_error(exc) from exc

            previous_assignments = {
                finding.id: finding.assigned_to
                for finding, _department_id in scoped_findings
            }
            for finding, _department_id in scoped_findings:
                finding.assigned_to = target.id

            await self.session.flush()
            for finding, _department_id in scoped_findings:
                previous = previous_assignments[finding.id]
                await self.audit(
                    action=AuditAction.ASSIGN_FINDING,
                    entity_type="ValidationFinding",
                    entity_id=finding.id,
                    description="Compliance finding assigned.",
                    old_values={
                        "status": finding.status.value,
                        "assignedTo": (str(previous) if previous is not None else None),
                    },
                    new_values={
                        "status": finding.status.value,
                        "assignedTo": str(target.id),
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return FindingBulkActionResponse(
            action="ASSIGN",
            processed_count=len(normalized_ids),
            finding_ids=normalized_ids,
        )

    async def bulk_review(
        self,
        finding_ids: Sequence[UUID],
        *,
        comment: str,
        maximum_items: int,
    ) -> FindingBulkActionResponse:
        """Start review for a bounded finding set as one transaction."""

        self._ensure_permission(Permission.FINDINGS_REVIEW)
        normalized_ids = self._bounded_bulk_ids(
            finding_ids,
            maximum_items=maximum_items,
        )
        try:
            scoped_findings = await self._scoped_findings_for_update(normalized_ids)
            validated: list[tuple[ValidationFinding, FindingStatus, str]] = []
            for finding, _department_id in scoped_findings:
                previous = finding.status
                try:
                    result = self.resolution.transition(
                        {"status": previous.value},
                        FindingStatus.IN_REVIEW.value,
                        actor_id=self.user.id,
                        comment=comment,
                    )
                except FindingTransitionError as exc:
                    raise transition_error(exc) from exc
                assert isinstance(result, dict)
                validated.append(
                    (
                        finding,
                        previous,
                        str(result["review_comment"]),
                    )
                )

            reviewed_at = utc_now()
            for finding, _previous, review_comment in validated:
                finding.status = FindingStatus.IN_REVIEW
                finding.reviewed_by = self.user.id
                finding.reviewed_at = reviewed_at
                finding.review_comment = review_comment

            await self.session.flush()
            for finding, previous, review_comment in validated:
                await self.audit(
                    action=AuditAction.REVIEW_FINDING,
                    entity_type="ValidationFinding",
                    entity_id=finding.id,
                    description=(
                        f"Finding status changed to {FindingStatus.IN_REVIEW.value}."
                    ),
                    old_values={"status": previous.value},
                    new_values={
                        "status": FindingStatus.IN_REVIEW.value,
                        "comment": review_comment,
                        "reason": None,
                        "acceptedRiskExpiryDate": None,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return FindingBulkActionResponse(
            action="REVIEW",
            processed_count=len(normalized_ids),
            finding_ids=normalized_ids,
        )

    async def _refresh_run_open_findings(
        self,
        finding: ValidationFinding,
    ) -> None:
        """Synchronize the mutable workflow counter under a run row lock."""

        if finding.compliance_run_id is None:
            return
        await self.session.scalar(
            select(ComplianceRun.id)
            .where(ComplianceRun.id == finding.compliance_run_id)
            .with_for_update()
        )
        open_count = (
            select(func.count(ValidationFinding.id))
            .where(
                ValidationFinding.compliance_run_id == finding.compliance_run_id,
                ValidationFinding.status.in_(_OPEN_FINDING_STATUSES),
            )
            .scalar_subquery()
        )
        await self.session.execute(
            update(ComplianceRun)
            .where(ComplianceRun.id == finding.compliance_run_id)
            .values(open_findings=open_count)
        )

    async def _transition(
        self,
        finding_id: UUID,
        *,
        permission: Permission,
        target: FindingStatus,
        action: AuditAction,
        comment: str | None = None,
        reason: str | None = None,
        expiry_date: date | None = None,
    ) -> FindingResponse:
        self._ensure_permission(permission)
        finding = await self._scoped_finding(
            finding_id,
            for_update=True,
        )
        previous = finding.status
        try:
            validated = self.resolution.transition(
                {"status": previous.value},
                target.value,
                actor_id=self.user.id,
                comment=comment,
                reason=reason,
                expiry_date=expiry_date,
            )
        except FindingTransitionError as exc:
            raise transition_error(exc) from exc

        assert isinstance(validated, dict)
        if target in {FindingStatus.IN_REVIEW, FindingStatus.OPEN}:
            comment = str(validated["review_comment"])
        elif target is FindingStatus.RESOLVED:
            comment = str(validated["resolution_comment"])
        elif target is FindingStatus.FALSE_POSITIVE:
            reason = str(validated["false_positive_reason"])
        elif target is FindingStatus.ACCEPTED_RISK:
            reason = str(validated["accepted_risk_reason"])
        elif target is FindingStatus.REOPENED:
            reason = str(validated["reopen_reason"])

        now = utc_now()
        finding.status = target
        if target is FindingStatus.IN_REVIEW:
            finding.reviewed_by = self.user.id
            finding.reviewed_at = now
            finding.review_comment = comment
        elif target is FindingStatus.RESOLVED:
            finding.resolved_by = self.user.id
            finding.resolved_at = now
            finding.resolution_comment = comment
        elif target is FindingStatus.FALSE_POSITIVE:
            finding.false_positive_by = self.user.id
            finding.false_positive_at = now
            finding.false_positive_reason = reason
        elif target is FindingStatus.ACCEPTED_RISK:
            finding.accepted_risk_by = self.user.id
            finding.accepted_risk_at = now
            finding.accepted_risk_reason = reason
            finding.accepted_risk_expiry_date = expiry_date
        elif target is FindingStatus.REOPENED:
            finding.reopened_by = self.user.id
            finding.reopened_at = now
            finding.reopen_reason = reason

        try:
            await self.session.flush()
            await self._refresh_run_open_findings(finding)
            await self.audit(
                action=action,
                entity_type="ValidationFinding",
                entity_id=finding.id,
                description=f"Finding status changed to {target.value}.",
                old_values={"status": previous.value},
                new_values={
                    "status": target.value,
                    "comment": comment,
                    "reason": reason,
                    "acceptedRiskExpiryDate": (
                        expiry_date.isoformat() if expiry_date is not None else None
                    ),
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._detail_response(await self._scoped_finding(finding.id))

    async def _detail_response(
        self,
        finding: ValidationFinding,
    ) -> FindingResponse:
        history = await self._history(finding)
        return finding_response(finding, history=history)

    async def _history(
        self,
        finding: ValidationFinding,
    ) -> builtins.list[FindingHistoryEntry]:
        """Load bounded workflow audit rows only after scoped finding lookup."""

        statement = (
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .where(
                AuditLog.entity_type == "ValidationFinding",
                AuditLog.entity_id == finding.id,
            )
            .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
            .limit(_MAX_FINDING_HISTORY_ITEMS)
        )
        rows = list((await self.session.scalars(statement)).all())
        history: list[FindingHistoryEntry] = []
        for row in rows:
            old_values = row.old_values_json or {}
            new_values = row.new_values_json or {}
            current_status = _finding_status(new_values.get("status"))
            if current_status is None:
                continue
            history.append(
                FindingHistoryEntry(
                    id=row.id,
                    action=row.action.value,
                    previous_status=_finding_status(old_values.get("status")),
                    new_status=current_status,
                    comment=_optional_history_text(new_values.get("comment")),
                    reason=_optional_history_text(new_values.get("reason")),
                    actor=user_reference(row.user),
                    created_at=row.created_at,
                )
            )
        return history

    async def _scoped_finding(
        self,
        finding_id: UUID,
        *,
        for_update: bool = False,
    ) -> ValidationFinding:
        department_ids = self._scope_department_ids()
        statement = (
            select(ValidationFinding)
            .join(
                Document,
                Document.id == ValidationFinding.document_id,
            )
            .options(*self._response_options())
            .where(ValidationFinding.id == finding_id)
            .execution_options(populate_existing=True)
        )
        if department_ids is not None:
            statement = statement.where(
                Document.department_id.in_(list(department_ids))
            )
        if for_update:
            statement = statement.with_for_update(of=ValidationFinding)
        finding = (await self.session.execute(statement)).scalar_one_or_none()
        if finding is None:
            raise finding_not_found()
        return finding

    async def _scoped_findings_for_update(
        self,
        finding_ids: Sequence[UUID],
    ) -> builtins.list[tuple[ValidationFinding, UUID]]:
        """Lock all visible rows in stable order, then restore request order."""

        department_ids = self._scope_department_ids()
        statement = (
            select(ValidationFinding, Document.department_id)
            .join(
                Document,
                Document.id == ValidationFinding.document_id,
            )
            .where(ValidationFinding.id.in_(list(finding_ids)))
            .order_by(ValidationFinding.id)
            .with_for_update(of=ValidationFinding)
            .execution_options(populate_existing=True)
        )
        if department_ids is not None:
            statement = statement.where(
                Document.department_id.in_(list(department_ids))
            )
        rows = list((await self.session.execute(statement)).all())
        if len(rows) != len(finding_ids):
            raise finding_not_found()
        by_id = {
            finding.id: (finding, department_id) for finding, department_id in rows
        }
        return [by_id[finding_id] for finding_id in finding_ids]

    async def _active_assignment_target(self, assigned_to: UUID) -> User:
        target = await self.users.get_by_id(assigned_to)
        if target is None or not target.is_active:
            raise document_error(
                "The assignment target must be an active user.",
                field="assignedTo",
                code="FINDING_ASSIGNEE_INVALID",
                title="Finding assignment is invalid.",
            )
        return target

    def _validate_assignment_department(
        self,
        target: User,
        department_id: UUID,
    ) -> None:
        if not self._view_all_departments and target.department_id != department_id:
            raise document_error(
                "The assignment target is outside the finding department.",
                field="assignedTo",
                code="FINDING_ASSIGNMENT_INVALID",
                title="Finding assignment is invalid.",
            )

    @staticmethod
    def _bounded_bulk_ids(
        finding_ids: Sequence[UUID],
        *,
        maximum_items: int,
    ) -> builtins.list[UUID]:
        normalized = list(dict.fromkeys(finding_ids))
        if not normalized:
            raise document_error(
                "At least one finding ID is required.",
                field="findingIds",
                code="FINDING_BULK_ACTION_EMPTY",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                title="Finding bulk action is invalid.",
            )
        if len(normalized) > maximum_items:
            raise document_error(
                (
                    "The bulk action exceeds the configured limit of "
                    f"{maximum_items} findings."
                ),
                field="findingIds",
                code="FINDING_BULK_ACTION_LIMIT_EXCEEDED",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                title="Finding bulk action is too large.",
            )
        return normalized

    def _filter_predicates(
        self,
        filters: FindingFilter,
        *,
        department_ids: Sequence[UUID] | None,
    ) -> builtins.list[Any]:
        predicates: list[Any] = []
        if department_ids is not None:
            predicates.append(Document.department_id.in_(list(department_ids)))
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            predicates.append(
                or_(
                    ValidationFinding.title.ilike(pattern),
                    ValidationFinding.description.ilike(pattern),
                    ValidationFinding.source_reference.ilike(pattern),
                )
            )
        optional_filters = (
            (filters.document_id, ValidationFinding.document_id),
            (
                filters.revision_id,
                ValidationFinding.document_revision_id,
            ),
            (
                filters.compliance_run_id,
                ValidationFinding.compliance_run_id,
            ),
            (
                filters.detected_section_id,
                ValidationFinding.detected_section_id,
            ),
            (filters.finding_code, ValidationFinding.finding_code),
            (filters.finding_type, ValidationFinding.finding_type),
            (filters.severity, ValidationFinding.severity),
            (filters.status, ValidationFinding.status),
            (filters.language_code, ValidationFinding.language_code),
            (filters.assigned_to, ValidationFinding.assigned_to),
        )
        predicates.extend(
            column == value for value, column in optional_filters if value is not None
        )
        if filters.section_code and filters.section_code.strip():
            canonical_code = filters.section_code.strip().upper()
            predicates.append(
                ValidationFinding.detected_section_id.in_(
                    select(DetectedSection.id).where(
                        func.upper(DetectedSection.canonical_code) == canonical_code
                    )
                )
            )
        if filters.created_by_system is not None:
            predicates.append(
                ValidationFinding.is_system_generated.is_(filters.created_by_system)
            )
        if filters.created_from is not None:
            predicates.append(ValidationFinding.created_at >= filters.created_from)
        if filters.created_to is not None:
            predicates.append(ValidationFinding.created_at <= filters.created_to)
        return predicates

    @staticmethod
    def _apply_sort(
        statement: Select[tuple[ValidationFinding]],
        *,
        sort_by: str,
        sort_order: str,
    ) -> Select[tuple[ValidationFinding]]:
        direction = sort_order.strip().lower()
        if direction not in {"asc", "desc"}:
            raise document_error(
                "sortOrder must be either asc or desc.",
                field="sortOrder",
                code="FINDING_SORT_ORDER_INVALID",
                title="Finding sort is invalid.",
            )
        normalized = sort_by.strip()
        ordering = asc if direction == "asc" else desc
        if normalized == "severity":
            severity_rank = case(
                (
                    ValidationFinding.severity == FindingSeverity.CRITICAL,
                    4,
                ),
                (
                    ValidationFinding.severity == FindingSeverity.MAJOR,
                    3,
                ),
                (
                    ValidationFinding.severity == FindingSeverity.MINOR,
                    2,
                ),
                else_=1,
            )
            return statement.order_by(
                ordering(severity_rank),
                desc(ValidationFinding.created_at),
                desc(ValidationFinding.id),
            )
        column = _SORT_FIELDS.get(normalized)
        if column is None:
            raise document_error(
                "sortBy is not a supported finding field.",
                field="sortBy",
                code="FINDING_SORT_FIELD_INVALID",
                title="Finding sort is invalid.",
            )
        secondary = (
            ()
            if column is ValidationFinding.created_at
            else (desc(ValidationFinding.created_at),)
        )
        return statement.order_by(
            ordering(column),
            *secondary,
            desc(ValidationFinding.id),
        )

    def _scope_department_ids(
        self,
        requested: UUID | None = None,
    ) -> Sequence[UUID] | None:
        if self._view_all_departments:
            return [requested] if requested is not None else None
        if self.user.department_id is None:
            raise document_error(
                "A department assignment is required for finding access.",
                code="FINDING_DEPARTMENT_SCOPE_DENIED",
                status_code=HTTPStatus.FORBIDDEN,
                title="Finding department scope was denied.",
            )
        if requested is not None and requested != self.user.department_id:
            raise document_error(
                "The requested department is outside your finding scope.",
                field="departmentId",
                code="FINDING_DEPARTMENT_SCOPE_DENIED",
                status_code=HTTPStatus.FORBIDDEN,
                title="Finding department scope was denied.",
            )
        return [self.user.department_id]

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

    @staticmethod
    def _validate_filter_window(filters: FindingFilter) -> None:
        if filters.created_from is None or filters.created_to is None:
            return
        try:
            invalid = filters.created_to < filters.created_from
        except TypeError as exc:
            raise document_error(
                "createdFrom and createdTo must use compatible time zones.",
                field="createdTo",
                code="FINDING_DATE_TIMEZONE_INVALID",
                title="Finding filter is invalid.",
            ) from exc
        if invalid:
            raise document_error(
                "createdTo must be greater than or equal to createdFrom.",
                field="createdTo",
                code="FINDING_DATE_RANGE_INVALID",
                title="Finding filter is invalid.",
            )

    @staticmethod
    def _response_options() -> tuple[Any, ...]:
        return (
            selectinload(ValidationFinding.document).selectinload(Document.department),
            selectinload(ValidationFinding.revision),
            selectinload(ValidationFinding.validation_rule),
            selectinload(ValidationFinding.detected_section),
            selectinload(ValidationFinding.occurrences),
            selectinload(ValidationFinding.previous_finding),
            selectinload(ValidationFinding.assignee),
            selectinload(ValidationFinding.reviewer),
            selectinload(ValidationFinding.resolver),
            selectinload(ValidationFinding.false_positive_actor),
            selectinload(ValidationFinding.accepted_risk_actor),
            selectinload(ValidationFinding.reopener),
        )


def finding_list_item(finding: ValidationFinding) -> FindingListItem:
    document = _loaded_relationship(finding, "document")
    revision = _loaded_relationship(finding, "revision")
    rule = _loaded_relationship(finding, "validation_rule")
    section = _loaded_relationship(finding, "detected_section")
    department = (
        _loaded_relationship(document, "department") if document is not None else None
    )
    return FindingListItem(
        id=finding.id,
        compliance_run_id=finding.compliance_run_id,
        document_id=finding.document_id,
        document_revision_id=finding.document_revision_id,
        document_file_id=finding.document_file_id,
        finding_code=finding.finding_code,
        finding_type=finding.finding_type,
        severity=finding.severity,
        status=finding.status,
        document=(
            ComplianceDocumentReference(
                id=document.id,
                base_document_code=document.base_document_code,
                title=document.title,
                department_id=document.department_id,
                department_name=(department.name if department is not None else None),
            )
            if document is not None
            else None
        ),
        revision=(
            ComplianceRevisionReference(
                id=revision.id,
                revision_code=revision.revision_code,
                full_document_code=revision.full_document_code,
            )
            if revision is not None
            else None
        ),
        validation_rule=(
            ComplianceRuleReference(
                id=rule.id,
                code=rule.code,
                name=rule.name,
                version=None,
            )
            if rule is not None
            else None
        ),
        title=finding.title,
        language_code=finding.language_code,
        detected_section_id=finding.detected_section_id,
        section_code=(section.canonical_code if section is not None else None),
        source_reference=_safe_source_reference(finding.source_reference),
        page_number=finding.page_number,
        worksheet_name=finding.worksheet_name,
        cell_coordinate=finding.cell_coordinate,
        assigned_to=(
            user_reference(_loaded_relationship(finding, "assignee"))
            or finding.assigned_to
        ),
        is_system_generated=finding.is_system_generated,
        is_repeat=finding.is_repeat,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


def finding_response(
    finding: ValidationFinding,
    *,
    history: Sequence[FindingHistoryEntry] = (),
) -> FindingResponse:
    item = finding_list_item(finding)
    return FindingResponse(
        **item.model_dump(),
        validation_rule_id=finding.validation_rule_id,
        description=finding.description,
        recommendation=finding.recommendation,
        container_id=finding.container_id,
        translation_group_id=finding.translation_group_id,
        extracted_block_id=finding.extracted_block_id,
        ocr_block_id=finding.ocr_block_id,
        location=_safe_mapping(finding.location_json),
        expected_value=_safe_json_value(finding.expected_value_json),
        actual_value=_safe_json_value(finding.actual_value_json),
        metrics=_safe_mapping(finding.metrics_json),
        previous_finding_id=finding.previous_finding_id,
        created_by=finding.created_by,
        reviewed_by=(
            user_reference(_loaded_relationship(finding, "reviewer"))
            or finding.reviewed_by
        ),
        reviewed_at=finding.reviewed_at,
        review_comment=finding.review_comment,
        resolved_by=(
            user_reference(_loaded_relationship(finding, "resolver"))
            or finding.resolved_by
        ),
        resolved_at=finding.resolved_at,
        resolution_comment=finding.resolution_comment,
        false_positive_by=(
            user_reference(_loaded_relationship(finding, "false_positive_actor"))
            or finding.false_positive_by
        ),
        false_positive_at=finding.false_positive_at,
        false_positive_reason=finding.false_positive_reason,
        accepted_risk_by=(
            user_reference(_loaded_relationship(finding, "accepted_risk_actor"))
            or finding.accepted_risk_by
        ),
        accepted_risk_at=finding.accepted_risk_at,
        accepted_risk_reason=finding.accepted_risk_reason,
        accepted_risk_expiry_date=finding.accepted_risk_expiry_date,
        reopened_by=(
            user_reference(_loaded_relationship(finding, "reopener"))
            or finding.reopened_by
        ),
        reopened_at=finding.reopened_at,
        reopen_reason=finding.reopen_reason,
        occurrences=[
            finding_occurrence_response(occurrence)
            for occurrence in (_loaded_relationship(finding, "occurrences") or ())
        ],
        history=list(history),
    )


def finding_occurrence_response(
    occurrence: FindingOccurrence,
) -> FindingOccurrenceResponse:
    return FindingOccurrenceResponse(
        id=occurrence.id,
        finding_id=occurrence.finding_id,
        compliance_run_id=occurrence.compliance_run_id,
        detected_at=occurrence.detected_at,
        source_reference=_safe_source_reference(occurrence.source_reference),
        location=_safe_mapping(occurrence.location_json),
        metrics=_safe_mapping(occurrence.metrics_json),
        created_at=occurrence.created_at,
    )


def finding_not_found(
    detail: str = "Finding does not exist or is outside your scope.",
    *,
    code: str = "FINDING_NOT_FOUND",
) -> Exception:
    return document_error(
        detail,
        code=code,
        status_code=HTTPStatus.NOT_FOUND,
        title="Finding was not found.",
    )


def transition_error(error: FindingTransitionError) -> Exception:
    return document_error(
        str(error),
        code=error.code,
        status_code=HTTPStatus.CONFLICT,
        title="Finding status transition is invalid.",
    )


def _audit_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _loaded_relationship(value: object | None, name: str) -> Any | None:
    """Return an already-loaded ORM relationship without issuing SQL."""

    if value is None:
        return None
    state = inspect(value, raiseerr=False)
    if state is None or name in state.unloaded:
        return None
    return getattr(value, name)


def user_reference(value: object | None) -> UserReference | None:
    if not isinstance(value, User):
        return None
    return UserReference(id=value.id, name=value.name)


def _finding_status(value: object) -> FindingStatus | None:
    if value is None:
        return None
    try:
        return FindingStatus(str(value))
    except ValueError:
        return None


def _optional_history_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_source_reference(value: str | None) -> str | None:
    return safe_source_reference(value) if value is not None else None


def _safe_mapping(value: object) -> dict[str, Any]:
    safe = json_safe(value or {})
    return safe if isinstance(safe, dict) else {}


def _safe_json_value(
    value: object,
) -> dict[str, Any] | list[Any] | None:
    if value is None:
        return None
    safe = json_safe(value)
    return safe if isinstance(safe, (dict, list)) else None


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)
