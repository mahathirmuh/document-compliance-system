"""Shared document-domain policy, validation, serialization, and audit helpers."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    AuditAction,
    Permission,
    UserRole,
    has_permission,
)
from app.core.exceptions import ApplicationError, AuthorizationError
from app.models.department import Department
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.user import User
from app.models.validation_rule import ValidationRule
from app.repositories.audit_log import AuditLogRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_status_repository import (
    DocumentStatusRepository,
)
from app.repositories.document_type_repository import DocumentTypeRepository
from app.repositories.section_repository import SectionRepository
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.common import ErrorDetail
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentResponse,
    DocumentRevisionSummary,
)
from app.schemas.document_revision import (
    DocumentRevisionListItem,
    DocumentRevisionResponse,
    MasterDataReference,
    UserReference,
)
from app.services.auth.auth_service import RequestMetadata


def document_error(
    message: str,
    *,
    field: str | None = None,
    code: str | None = None,
    status_code: int = HTTPStatus.BAD_REQUEST,
    title: str = "Document validation failed.",
) -> ApplicationError:
    return ApplicationError(
        title,
        status_code=status_code,
        errors=[ErrorDetail(field=field, message=message, code=code)],
    )


def document_not_found() -> ApplicationError:
    return document_error(
        "Document does not exist or was deleted.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Document was not found.",
    )


def revision_not_found() -> ApplicationError:
    return document_error(
        "Document revision does not exist or was deleted.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Document revision was not found.",
    )


def document_conflict(
    message: str,
    *,
    field: str | None = None,
    code: str | None = None,
    title: str = "Document could not be saved.",
) -> ApplicationError:
    return document_error(
        message,
        field=field,
        code=code,
        status_code=HTTPStatus.CONFLICT,
        title=title,
    )


class DocumentAccessPolicy:
    """One backend-authoritative department scope implementation."""

    def __init__(self, user: User) -> None:
        self.user = user

    @property
    def view_all_departments(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        )

    @property
    def scope_department_id(self) -> UUID | None:
        return None if self.view_all_departments else self.user.department_id

    def ensure_document_access(self, document: Document) -> None:
        if not self.view_all_departments and (
            self.user.department_id is None
            or document.department_id != self.user.department_id
        ):
            raise AuthorizationError("This document is outside your department scope.")

    def ensure_create_department(self, department_id: UUID) -> None:
        if self.view_all_departments:
            return
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department must be assigned to your user profile before "
                "creating documents."
            )
        if department_id != self.user.department_id:
            raise AuthorizationError(
                "Documents may only be created for your assigned department."
            )

    def ensure_department_change(self, department_id: UUID) -> None:
        if not self.view_all_departments and department_id != self.user.department_id:
            raise AuthorizationError(
                "You cannot move a document to another department."
            )

    @property
    def can_change_published_code(self) -> bool:
        return self.user.is_superuser or self.user.role in {
            UserRole.SUPER_ADMIN,
            UserRole.DOCUMENT_CONTROLLER,
        }


def master_reference(entity: Any | None) -> MasterDataReference | None:
    if entity is None:
        return None
    return MasterDataReference(
        id=entity.id,
        code=entity.code,
        name=entity.name,
    )


def user_reference(entity: User | None) -> UserReference | None:
    if entity is None:
        return None
    return UserReference(id=entity.id, name=entity.name)


def revision_list_item(
    revision: DocumentRevision,
) -> DocumentRevisionListItem:
    status = master_reference(revision.document_status)
    assert status is not None
    return DocumentRevisionListItem(
        id=revision.id,
        document_id=revision.document_id,
        revision_code=revision.revision_code,
        revision_number=revision.revision_number,
        full_document_code=revision.full_document_code,
        document_status_id=revision.document_status_id,
        validation_rule_id=revision.validation_rule_id,
        status=status,
        validation_rule=master_reference(revision.validation_rule),
        issue_date=revision.issue_date,
        effective_date=revision.effective_date,
        review_date=revision.review_date,
        expiry_date=revision.expiry_date,
        sharepoint_url=revision.sharepoint_url,
        external_reference=revision.external_reference,
        remarks=revision.remarks,
        is_current=revision.is_current,
        is_superseded=revision.is_superseded,
        superseded_at=revision.superseded_at,
        superseded_by_revision_id=revision.superseded_by_revision_id,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
    )


def revision_response(
    revision: DocumentRevision,
) -> DocumentRevisionResponse:
    item = revision_list_item(revision)
    return DocumentRevisionResponse(
        **item.model_dump(),
        created_by=user_reference(revision.creator),
        updated_by=user_reference(revision.updater),
    )


def revision_summary(
    revision: DocumentRevision | None,
) -> DocumentRevisionSummary | None:
    if revision is None:
        return None
    status = master_reference(revision.document_status)
    assert status is not None
    return DocumentRevisionSummary(
        id=revision.id,
        document_id=revision.document_id,
        revision_code=revision.revision_code,
        revision_number=revision.revision_number,
        full_document_code=revision.full_document_code,
        document_status_id=revision.document_status_id,
        validation_rule_id=revision.validation_rule_id,
        status=status,
        validation_rule=master_reference(revision.validation_rule),
        issue_date=revision.issue_date,
        effective_date=revision.effective_date,
        review_date=revision.review_date,
        expiry_date=revision.expiry_date,
        sharepoint_url=revision.sharepoint_url,
        external_reference=revision.external_reference,
        remarks=revision.remarks,
        is_current=revision.is_current,
        is_superseded=revision.is_superseded,
    )


def document_list_item(document: Document) -> DocumentListItem:
    department = master_reference(document.department)
    document_type = master_reference(document.document_type)
    assert department is not None and document_type is not None
    return DocumentListItem(
        id=document.id,
        company_code=document.company_code,
        department_id=document.department_id,
        section_id=document.section_id,
        document_type_id=document.document_type_id,
        document_number=document.document_number,
        base_document_code=document.base_document_code,
        title=document.title,
        department=department,
        section=master_reference(document.section),
        document_type=document_type,
        current_revision=revision_summary(document.current_revision),
        is_archived=document.is_archived,
        updated_at=document.updated_at,
    )


def document_response(
    document: Document,
    *,
    detail: bool = False,
) -> DocumentResponse | DocumentDetailResponse:
    item = document_list_item(document)
    values = {
        **item.model_dump(),
        "description": document.description,
        "owner_department": master_reference(document.owner_department),
        "owner_department_id": document.owner_department_id,
        "document_owner_name": document.document_owner_name,
        "current_revision_id": document.current_revision_id,
        "archived_at": document.archived_at,
        "archived_by": user_reference(document.archiver),
        "archive_reason": document.archive_reason,
        "created_by": user_reference(document.creator),
        "updated_by": user_reference(document.updater),
        "created_at": document.created_at,
    }
    if detail:
        return DocumentDetailResponse(
            **values,
            revisions=[
                revision_list_item(revision)
                for revision in document.revisions
                if revision.deleted_at is None
            ],
        )
    return DocumentResponse(**values)


class DocumentServiceBase:
    """Common repositories, policy, validation, and audit operations."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.user = user
        self.metadata = metadata
        self.policy = DocumentAccessPolicy(user)
        self.audit_logs = AuditLogRepository(session)
        self.departments = DepartmentRepository(session)
        self.sections = SectionRepository(session)
        self.document_types = DocumentTypeRepository(session)
        self.document_statuses = DocumentStatusRepository(session)
        self.validation_rules = ValidationRuleRepository(session)

    async def audit(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        entity_id: UUID | None,
        description: str,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        await self.audit_logs.create(
            user_id=self.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
        )

    async def active_department(
        self,
        department_id: UUID,
        *,
        field: str = "departmentId",
    ) -> Department:
        department = await self.departments.get_by_id(department_id)
        if department is None:
            raise document_error("Department was not found.", field=field)
        if not department.is_active:
            raise document_error("Department must be active.", field=field)
        return department

    async def existing_department(
        self,
        department_id: UUID,
        *,
        field: str,
    ) -> Department:
        department = await self.departments.get_by_id(department_id)
        if department is None:
            raise document_error("Department was not found.", field=field)
        return department

    async def active_document_type(
        self,
        document_type_id: UUID,
    ) -> DocumentType:
        document_type = await self.document_types.get_by_id(document_type_id)
        if document_type is None:
            raise document_error(
                "Document type was not found.",
                field="documentTypeId",
            )
        if not document_type.is_active:
            raise document_error(
                "Document type must be active.",
                field="documentTypeId",
            )
        return document_type

    async def resolve_status(
        self,
        document_status_id: UUID | None,
    ) -> DocumentStatus:
        status = (
            await self.document_statuses.get_by_id(document_status_id)
            if document_status_id is not None
            else await self.document_statuses.get_initial()
        )
        if status is None:
            raise document_error(
                (
                    "Document status was not found."
                    if document_status_id is not None
                    else "No initial document status is configured."
                ),
                field="documentStatusId",
            )
        if not status.is_active:
            raise document_error(
                "Document status must be active.",
                field="documentStatusId",
            )
        return status

    async def resolve_validation_rule(
        self,
        document_type: DocumentType,
        validation_rule_id: UUID | None,
    ) -> ValidationRule | None:
        rule: ValidationRule | None
        if validation_rule_id is not None:
            rule = await self.validation_rules.get_by_id(validation_rule_id)
        else:
            rule = None
            if document_type.default_validation_rule_id is not None:
                rule = await self.validation_rules.get_by_id(
                    document_type.default_validation_rule_id
                )
            if rule is None:
                rule = await self.validation_rules.get_default(document_type.id)
            if rule is None:
                rule = await self.validation_rules.get_default(None)
        if validation_rule_id is not None and rule is None:
            raise document_error(
                "Validation rule was not found.",
                field="validationRuleId",
            )
        if rule is not None:
            if not rule.is_active:
                raise document_error(
                    "Validation rule must be active.",
                    field="validationRuleId",
                )
            if rule.document_type_id not in (None, document_type.id):
                raise document_error(
                    "Validation rule does not apply to this document type.",
                    field="validationRuleId",
                )
        return rule
