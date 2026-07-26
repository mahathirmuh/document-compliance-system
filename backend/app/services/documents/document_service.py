"""Document identity workflows, department scope, parsing, and bulk actions."""

from __future__ import annotations

import builtins
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.core.exceptions import ApplicationError
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.document_type import DocumentType
from app.models.section import Section
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.schemas.document import (
    BulkArchiveRequest,
    BulkDocumentItemResult,
    BulkDocumentResult,
    BulkRestoreRequest,
    BulkUpdateStatusRequest,
    DocumentArchiveRequest,
    DocumentCreate,
    DocumentDetailResponse,
    DocumentFilter,
    DocumentListResponse,
    DocumentParseResponse,
    DocumentRestoreRequest,
    DocumentUpdate,
)
from app.schemas.document_revision import MasterDataReference
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
    document_list_item,
    document_not_found,
    document_response,
    master_reference,
)
from app.services.documents.date_filter import created_at_utc_bounds
from app.services.documents.document_code_service import (
    DocumentCodeError,
    DocumentCodeService,
    ParsedDocumentCode,
)
from app.utils.datetime import utc_now

BulkDocumentOperation = Literal["archive", "restore", "update-status"]


class DocumentService(DocumentServiceBase):
    """Own atomic document-register identity workflows."""

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
        self.codes = DocumentCodeService()

    async def list(
        self,
        filters: DocumentFilter,
    ) -> DocumentListResponse:
        values = filters.model_dump(by_alias=False)
        created_from = values.pop("created_from")
        created_to = values.pop("created_to")
        (
            values["created_from_utc"],
            values["created_to_utc_exclusive"],
        ) = created_at_utc_bounds(
            created_from,
            created_to,
            self.settings.application_timezone,
        )
        items, total = await self.documents.list(
            **values,
            scope_all_departments=self.policy.view_all_departments,
            scope_department_id=self.policy.scope_department_id,
        )
        return DocumentListResponse(
            items=[document_list_item(item) for item in items],
            page=filters.page,
            pageSize=filters.page_size,
            totalItems=total,
            totalPages=(
                (total + filters.page_size - 1) // filters.page_size
                if total
                else 0
            ),
        )

    async def get(self, document_id: UUID) -> DocumentDetailResponse:
        document = await self.documents.get_detail(document_id)
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        response = document_response(document, detail=True)
        assert isinstance(response, DocumentDetailResponse)
        return response

    async def create(
        self,
        payload: DocumentCreate,
        *,
        commit: bool = True,
    ) -> DocumentDetailResponse:
        (
            department,
            section,
            document_type,
            base_code,
        ) = await self._validate_identity(
            company_code=(
                payload.company_code or self.settings.default_company_code
            ),
            department_id=payload.department_id,
            section_id=payload.section_id,
            document_type_id=payload.document_type_id,
            document_number=payload.document_number,
        )
        self.policy.ensure_create_department(department.id)
        if len(payload.title) > self.settings.document_title_max_length:
            raise document_error(
                "Title exceeds the configured maximum length.",
                field="title",
            )
        if await self.documents.exists_by_base_code(base_code):
            raise document_conflict(
                f"Document {base_code} already exists.",
                field="documentNumber",
                title="Document could not be created.",
            )
        owner_department_id = (
            payload.owner_department_id or department.id
        )
        await self.active_department(
            owner_department_id,
            field="ownerDepartmentId",
        )
        document = Document(
            company_code=(
                payload.company_code or self.settings.default_company_code
            ),
            department_id=department.id,
            section_id=section.id if section is not None else None,
            document_type_id=document_type.id,
            document_number=payload.document_number,
            base_document_code=base_code,
            title=payload.title,
            description=payload.description,
            owner_department_id=owner_department_id,
            document_owner_name=payload.document_owner_name,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.documents.create(document)
            created_revision: DocumentRevision | None = None
            if payload.initial_revision is not None:
                created_revision = await self._create_revision(
                    document,
                    document_type,
                    payload.initial_revision,
                )
            await self.audit(
                action=AuditAction.CREATE_DOCUMENT,
                entity_type="document",
                entity_id=document.id,
                description=f"Created document {base_code}.",
                new_values=self._audit_values(document),
            )
            if created_revision is not None:
                await self.audit(
                    action=AuditAction.CREATE_DOCUMENT_REVISION,
                    entity_type="document_revision",
                    entity_id=created_revision.id,
                    description=(
                        f"Created initial revision "
                        f"{created_revision.full_document_code}."
                    ),
                    new_values={
                        "documentId": str(document.id),
                        "baseDocumentCode": base_code,
                        "revisionId": str(created_revision.id),
                        "revisionCode": created_revision.revision_code,
                        "fullDocumentCode": (
                            created_revision.full_document_code
                        ),
                    },
                )
            if commit:
                await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                f"Document {base_code} or its revision already exists.",
                field="documentNumber",
                title="Document could not be created.",
            ) from exc
        result = await self.documents.get_detail(document.id)
        assert result is not None
        response = document_response(result, detail=True)
        assert isinstance(response, DocumentDetailResponse)
        return response

    async def update(
        self,
        document_id: UUID,
        payload: DocumentUpdate,
    ) -> DocumentDetailResponse:
        document = await self.documents.get_detail(
            document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        if document.is_archived:
            raise document_error(
                "Archived documents are read-only until restored.",
                field=None,
            )
        changes = payload.model_dump(
            by_alias=False,
            exclude_unset=True,
        )
        reason = changes.pop("change_reason", None)
        if (
            reason is not None
            and len(reason) > self.settings.archive_reason_max_length
        ):
            raise document_error(
                "Change reason exceeds the configured maximum length.",
                field="changeReason",
            )
        old_values = self._audit_values(document)
        identity_fields = {
            "company_code",
            "department_id",
            "section_id",
            "document_type_id",
            "document_number",
        }
        identity_requested = bool(identity_fields.intersection(changes))
        code_changed = False
        old_code = document.base_document_code
        if identity_requested:
            required_fields = (
                "company_code",
                "department_id",
                "document_type_id",
                "document_number",
            )
            for field in required_fields:
                if field in changes and changes[field] is None:
                    raise document_error(
                        f"{field} cannot be null.",
                        field=self._camel(field),
                    )
            new_department_id = changes.get(
                "department_id",
                document.department_id,
            )
            self.policy.ensure_department_change(new_department_id)
            (
                department,
                section,
                document_type,
                new_code,
            ) = await self._validate_identity(
                company_code=changes.get(
                    "company_code",
                    document.company_code,
                ),
                department_id=new_department_id,
                section_id=changes.get("section_id", document.section_id),
                document_type_id=changes.get(
                    "document_type_id",
                    document.document_type_id,
                ),
                document_number=changes.get(
                    "document_number",
                    document.document_number,
                ),
                existing_document=document,
            )
            code_changed = new_code != old_code
            if code_changed:
                if not reason:
                    raise document_error(
                        "changeReason is required when changing document code.",
                        field="changeReason",
                    )
                if await self.documents.exists_by_base_code(
                    new_code,
                    exclude_id=document.id,
                ):
                    raise document_conflict(
                        f"Document {new_code} already exists.",
                        field="documentNumber",
                    )
                published = any(
                    revision.document_status.is_final
                    or revision.document_status.code == "EFFECTIVE"
                    or revision.effective_date is not None
                    for revision in document.revisions
                    if revision.deleted_at is None
                )
                if published and not self.policy.can_change_published_code:
                    raise document_error(
                        "Only a Super Admin or Document Controller may change "
                        "the code of a final or effective document.",
                        field="changeReason",
                        status_code=403,
                        title="Authorization failed.",
                    )
                for revision in document.revisions:
                    if revision.deleted_at is not None:
                        continue
                    full_code = self.codes.generate_full_document_code(
                        new_code,
                        revision.revision_code,
                    )
                    if await self.revisions.exists_by_full_code(
                        full_code,
                        exclude_id=revision.id,
                    ):
                        raise document_conflict(
                            f"Revision code {full_code} already exists.",
                            field="documentNumber",
                        )
                    revision.full_document_code = full_code
                    revision.updated_by = self.user.id
                document.base_document_code = new_code
            document.company_code = changes.get(
                "company_code",
                document.company_code,
            )
            document.department_id = department.id
            document.section_id = section.id if section is not None else None
            document.document_type_id = document_type.id
            document.department = department
            document.section = section
            document.document_type = document_type
            document.document_number = changes.get(
                "document_number",
                document.document_number,
            )

        if "title" in changes:
            if changes["title"] is None:
                raise document_error("title cannot be null.", field="title")
            if (
                len(changes["title"])
                > self.settings.document_title_max_length
            ):
                raise document_error(
                    "Title exceeds the configured maximum length.",
                    field="title",
                )
            document.title = changes["title"]
        if "description" in changes:
            document.description = changes["description"]
        if "document_owner_name" in changes:
            document.document_owner_name = changes["document_owner_name"]
        if "owner_department_id" in changes:
            owner_id = changes["owner_department_id"]
            if owner_id != document.owner_department_id:
                owner_department = None
                if owner_id is not None:
                    owner_department = await self.active_department(
                        owner_id,
                        field="ownerDepartmentId",
                    )
                document.owner_department_id = owner_id
                document.owner_department = owner_department
        document.updated_by = self.user.id

        action = (
            AuditAction.CHANGE_DOCUMENT_CODE
            if code_changed
            else AuditAction.UPDATE_DOCUMENT
        )
        try:
            await self.session.flush()
            await self.audit(
                action=action,
                entity_type="document",
                entity_id=document.id,
                description=(
                    f"Changed document code from {old_code} to "
                    f"{document.base_document_code}."
                    if code_changed
                    else f"Updated document {document.base_document_code}."
                ),
                old_values=old_values,
                new_values={
                    **self._audit_values(document),
                    "reason": reason,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "The requested document or revision code already exists.",
                field="documentNumber",
            ) from exc
        result = await self.documents.get_detail(document.id)
        assert result is not None
        response = document_response(result, detail=True)
        assert isinstance(response, DocumentDetailResponse)
        return response

    async def archive(
        self,
        document_id: UUID,
        payload: DocumentArchiveRequest,
    ) -> DocumentDetailResponse:
        document = await self.documents.get_detail(
            document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        if document.is_archived:
            raise document_conflict(
                "Document is already archived.",
                field=None,
            )
        if len(payload.reason) > self.settings.archive_reason_max_length:
            raise document_error(
                "Archive reason exceeds the configured maximum length.",
                field="reason",
            )
        old_values = self._audit_values(document)
        await self.documents.archive(
            document,
            archived_at=utc_now(),
            archived_by=self.user.id,
            reason=payload.reason,
        )
        document.updated_by = self.user.id
        await self.audit(
            action=AuditAction.ARCHIVE_DOCUMENT,
            entity_type="document",
            entity_id=document.id,
            description=f"Archived document {document.base_document_code}.",
            old_values=old_values,
            new_values={
                **self._audit_values(document),
                "reason": payload.reason,
            },
        )
        await self.session.commit()
        result = await self.documents.get_detail(document.id)
        assert result is not None
        response = document_response(result, detail=True)
        assert isinstance(response, DocumentDetailResponse)
        return response

    async def restore(
        self,
        document_id: UUID,
        payload: DocumentRestoreRequest | None,
    ) -> DocumentDetailResponse:
        document = await self.documents.get_detail(
            document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        if not document.is_archived:
            raise document_conflict(
                "Document is not archived.",
                field=None,
            )
        if await self.documents.exists_by_base_code(
            document.base_document_code,
            exclude_id=document.id,
        ):
            raise document_conflict(
                f"Document {document.base_document_code} already exists.",
                field="baseDocumentCode",
                title="Document could not be restored.",
            )
        old_values = self._audit_values(document)
        reason = payload.reason if payload is not None else None
        if (
            reason is not None
            and len(reason) > self.settings.archive_reason_max_length
        ):
            raise document_error(
                "Restore reason exceeds the configured maximum length.",
                field="reason",
            )
        await self.documents.restore(document)
        document.updated_by = self.user.id
        await self.audit(
            action=AuditAction.RESTORE_DOCUMENT,
            entity_type="document",
            entity_id=document.id,
            description=f"Restored document {document.base_document_code}.",
            old_values=old_values,
            new_values={
                **self._audit_values(document),
                "reason": reason,
            },
        )
        await self.session.commit()
        result = await self.documents.get_detail(document.id)
        assert result is not None
        response = document_response(result, detail=True)
        assert isinstance(response, DocumentDetailResponse)
        return response

    async def parse_code(self, value: str) -> DocumentParseResponse:
        candidates: builtins.list[ParsedDocumentCode] = []
        errors: builtins.list[str] = []
        for has_section in (True, False):
            try:
                parsed_candidates = self.codes.parse_document_code_candidates(
                    value,
                    has_section=has_section,
                )
            except DocumentCodeError as exc:
                errors.append(str(exc))
                continue
            for candidate in parsed_candidates:
                if candidate not in candidates:
                    candidates.append(candidate)

        resolved: builtins.list[
            tuple[
                ParsedDocumentCode,
                Any,
                Section | None,
                DocumentType,
                builtins.list[str],
            ]
        ] = []
        for candidate in candidates:
            try:
                resolution = await self._resolve_parsed_candidate(candidate)
            except ApplicationError as exc:
                if exc.errors:
                    errors.extend(error.message for error in exc.errors)
                else:
                    errors.append(exc.message)
                continue
            resolved.append((candidate, *resolution))
        if not resolved:
            message = next(
                (
                    error
                    for error in errors
                    if "does not belong" in error
                ),
                errors[-1] if errors else "Document code is invalid.",
            )
            raise document_error(message, field="value")
        if len(resolved) > 1:
            raise document_error(
                "Document code is ambiguous. Verify the section and document "
                "type components.",
                field="value",
            )
        candidate, department, section, document_type, warnings = resolved[0]
        department_ref = master_reference(department)
        document_type_ref = master_reference(document_type)
        assert (
            isinstance(department_ref, MasterDataReference)
            and isinstance(document_type_ref, MasterDataReference)
        )
        return DocumentParseResponse(
            company_code=candidate.company_code,
            department=department_ref,
            section=master_reference(section),
            document_type=document_type_ref,
            document_number=candidate.document_number,
            document_title=candidate.document_title,
            base_document_code=candidate.base_document_code,
            revision_code=candidate.revision_code,
            full_document_code=candidate.full_document_code,
            file_extension=candidate.file_extension,
            warnings=warnings,
        )

    async def bulk_archive(
        self,
        payload: BulkArchiveRequest,
    ) -> BulkDocumentResult:
        return await self._bulk(
            operation="archive",
            document_ids=payload.document_ids,
            reason=payload.reason,
        )

    async def bulk_restore(
        self,
        payload: BulkRestoreRequest,
    ) -> BulkDocumentResult:
        return await self._bulk(
            operation="restore",
            document_ids=payload.document_ids,
            reason=None,
        )

    async def bulk_update_status(
        self,
        payload: BulkUpdateStatusRequest,
    ) -> BulkDocumentResult:
        return await self._bulk(
            operation="update-status",
            document_ids=payload.document_ids,
            reason=payload.reason,
            document_status_id=payload.document_status_id,
        )

    async def _bulk(
        self,
        *,
        operation: BulkDocumentOperation,
        document_ids: builtins.list[UUID],
        reason: str | None,
        document_status_id: UUID | None = None,
    ) -> BulkDocumentResult:
        if (
            reason is not None
            and len(reason) > self.settings.archive_reason_max_length
        ):
            raise document_error(
                "Reason exceeds the configured maximum length.",
                field="reason",
            )
        status = (
            await self.resolve_status(document_status_id)
            if operation == "update-status"
            else None
        )
        results: builtins.list[BulkDocumentItemResult] = []
        changed: builtins.list[str] = []
        item_changes: builtins.list[dict[str, Any]] = []
        for document_id in sorted(
            dict.fromkeys(document_ids),
            key=str,
        ):
            document = await self.documents.get_detail(
                document_id,
                for_update=True,
            )
            if document is None:
                results.append(
                    BulkDocumentItemResult(
                        document_id=document_id,
                        success=False,
                        message="Document was not found.",
                    )
                )
                continue
            try:
                self.policy.ensure_document_access(document)
                revision = document.current_revision
                revision_id = (
                    str(revision.id) if revision is not None else None
                )
                old_values: dict[str, Any]
                new_values: dict[str, Any]
                if operation == "archive":
                    if document.is_archived:
                        raise document_error("Document is already archived.")
                    old_values = {
                        "isArchived": document.is_archived,
                        "archivedBy": (
                            str(document.archived_by)
                            if document.archived_by is not None
                            else None
                        ),
                        "archiveReason": document.archive_reason,
                    }
                    await self.documents.archive(
                        document,
                        archived_at=utc_now(),
                        archived_by=self.user.id,
                        reason=reason or "",
                    )
                    new_values = {
                        "isArchived": document.is_archived,
                        "archivedBy": str(self.user.id),
                        "archiveReason": document.archive_reason,
                    }
                elif operation == "restore":
                    if not document.is_archived:
                        raise document_error("Document is not archived.")
                    if await self.documents.exists_by_base_code(
                        document.base_document_code,
                        exclude_id=document.id,
                    ):
                        raise document_conflict(
                            "Document code conflicts with another document."
                        )
                    old_values = {
                        "isArchived": document.is_archived,
                        "archivedBy": (
                            str(document.archived_by)
                            if document.archived_by is not None
                            else None
                        ),
                        "archiveReason": document.archive_reason,
                    }
                    await self.documents.restore(document)
                    new_values = {
                        "isArchived": document.is_archived,
                        "archivedBy": None,
                        "archiveReason": None,
                    }
                else:
                    if document.is_archived:
                        raise document_error(
                            "Archived documents are read-only."
                        )
                    if document.current_revision is None:
                        raise document_error(
                            "Document has no current revision."
                        )
                    assert status is not None
                    revision = document.current_revision
                    revision_id = str(revision.id)
                    old_values = {
                        "documentStatusId": str(
                            revision.document_status_id
                        ),
                        "documentStatusCode": (
                            revision.document_status.code
                        ),
                    }
                    revision.document_status_id = status.id
                    revision.document_status = status
                    revision.updated_by = self.user.id
                    new_values = {
                        "documentStatusId": str(status.id),
                        "documentStatusCode": status.code,
                    }
                document.updated_by = self.user.id
                changed.append(str(document.id))
                if len(item_changes) < 100:
                    item_changes.append(
                        {
                            "documentId": str(document.id),
                            "baseDocumentCode": (
                                document.base_document_code
                            ),
                            "revisionId": revision_id,
                            "oldValues": old_values,
                            "newValues": new_values,
                        }
                    )
                results.append(
                    BulkDocumentItemResult(
                        document_id=document.id,
                        success=True,
                        message=f"Document {operation} succeeded.",
                    )
                )
            except ApplicationError as exc:
                message = (
                    exc.errors[0].message
                    if exc.errors
                    else exc.message
                )
                results.append(
                    BulkDocumentItemResult(
                        document_id=document.id,
                        success=False,
                        message=message,
                    )
                )
        action = {
            "archive": AuditAction.BULK_ARCHIVE_DOCUMENTS,
            "restore": AuditAction.BULK_RESTORE_DOCUMENTS,
            "update-status": AuditAction.BULK_UPDATE_DOCUMENT_STATUS,
        }[operation]
        await self.session.flush()
        await self.audit(
            action=action,
            entity_type="document_bulk",
            entity_id=None,
            description=f"Bulk document {operation} completed.",
            new_values={
                "documentIds": changed,
                "reason": reason,
                "documentStatusId": (
                    str(document_status_id)
                    if document_status_id is not None
                    else None
                ),
                "changeCount": len(changed),
                "changes": item_changes,
            },
        )
        await self.session.commit()
        succeeded = sum(item.success for item in results)
        return BulkDocumentResult(
            operation=operation,
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )

    async def _validate_identity(
        self,
        *,
        company_code: str,
        department_id: UUID,
        section_id: UUID | None,
        document_type_id: UUID,
        document_number: str,
        existing_document: Document | None = None,
    ) -> tuple[Any, Section | None, DocumentType, str]:
        department = (
            await self.existing_department(
                department_id,
                field="departmentId",
            )
            if (
                existing_document is not None
                and department_id == existing_document.department_id
            )
            else await self.active_department(department_id)
        )
        if (
            existing_document is not None
            and document_type_id == existing_document.document_type_id
        ):
            document_type = await self.document_types.get_by_id(
                document_type_id
            )
            if document_type is None:
                raise document_error(
                    "Document type was not found.",
                    field="documentTypeId",
                )
        else:
            document_type = await self.active_document_type(document_type_id)
        section: Section | None = None
        if document_type.requires_section:
            if section_id is None:
                raise document_error(
                    "Section is required for this document type.",
                    field="sectionId",
                )
            section = await self.sections.get_by_id(section_id)
            if section is None:
                raise document_error(
                    "Section was not found.",
                    field="sectionId",
                )
            if section.department_id != department.id:
                raise document_error(
                    "Section does not belong to the selected department.",
                    field="sectionId",
                )
            if (
                not section.is_active
                and (
                    existing_document is None
                    or section.id != existing_document.section_id
                )
            ):
                raise document_error(
                    "Section must be active.",
                    field="sectionId",
                )
        elif section_id is not None:
            raise document_error(
                "Section must be empty for this document type.",
                field="sectionId",
            )
        if (
            len(document_number)
            > self.settings.document_number_max_length
        ):
            raise document_error(
                "Document number exceeds the configured maximum length.",
                field="documentNumber",
            )
        try:
            base_code = self.codes.generate_base_document_code(
                company_code=company_code,
                department_code=department.code,
                section_code=section.code if section is not None else None,
                document_type_code=document_type.code,
                document_number=document_number,
                requires_section=document_type.requires_section,
            )
        except DocumentCodeError as exc:
            raise document_error(
                str(exc),
                field="documentNumber",
            ) from exc
        return department, section, document_type, base_code

    async def _create_revision(
        self,
        document: Document,
        document_type: DocumentType,
        payload: Any,
    ) -> DocumentRevision:
        status = await self.resolve_status(payload.document_status_id)
        rule = await self.resolve_validation_rule(
            document_type,
            payload.validation_rule_id,
        )
        revision_code = self.codes.normalize_revision_code(
            payload.revision_code
        )
        revision = DocumentRevision(
            document_id=document.id,
            revision_code=revision_code,
            revision_number=self.codes.revision_number(revision_code),
            full_document_code=self.codes.generate_full_document_code(
                document.base_document_code,
                revision_code,
            ),
            document_status_id=status.id,
            validation_rule_id=rule.id if rule is not None else None,
            issue_date=payload.issue_date,
            effective_date=payload.effective_date,
            review_date=payload.review_date,
            expiry_date=payload.expiry_date,
            sharepoint_url=payload.sharepoint_url,
            external_reference=payload.external_reference,
            remarks=payload.remarks,
            # A revision created together with its document is always current.
            is_current=True,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        await self.revisions.create(revision)
        document.current_revision_id = revision.id
        await self.session.flush()
        return revision

    async def _resolve_parsed_candidate(
        self,
        candidate: ParsedDocumentCode,
    ) -> tuple[
        Any,
        Section | None,
        DocumentType,
        builtins.list[str],
    ]:
        department = await self.departments.get_by_code(
            candidate.department_code
        )
        if department is None:
            raise document_error(
                f'Department code "{candidate.department_code}" was not found.',
                field="value",
            )
        document_type = await self.document_types.get_by_code(
            candidate.document_type_code
        )
        if document_type is None:
            raise document_error(
                f'Document Type code "{candidate.document_type_code}" '
                "was not found.",
                field="value",
            )
        section: Section | None = None
        if candidate.section_code is not None:
            section = await self.sections.get_by_department_and_code(
                department.id,
                candidate.section_code,
            )
            if section is None:
                any_section = await self.session.scalar(
                    select(Section).where(
                        Section.code == candidate.section_code,
                        Section.deleted_at.is_(None),
                    )
                )
                if any_section is not None:
                    raise document_error(
                        f'Section code "{candidate.section_code}" does not '
                        f'belong to Department "{department.code}".',
                        field="value",
                    )
                raise document_error(
                    f'Section code "{candidate.section_code}" was not found.',
                    field="value",
                )
        if document_type.requires_section and section is None:
            raise document_error(
                f'Document Type "{document_type.code}" requires a section.',
                field="value",
            )
        if not document_type.requires_section and section is not None:
            raise document_error(
                f'Document Type "{document_type.code}" does not use a section.',
                field="value",
            )
        warnings: builtins.list[str] = []
        existing = await self.documents.get_by_base_code(
            candidate.base_document_code
        )
        if not department.is_active:
            if existing is None:
                raise document_error(
                    f'Department "{department.code}" is inactive.',
                    field="value",
                )
            warnings.append(
                f'Department "{department.code}" is inactive but the '
                "document already exists."
            )
        if section is not None and not section.is_active:
            if existing is None:
                raise document_error(
                    f'Section "{section.code}" is inactive.',
                    field="value",
                )
            warnings.append(
                f'Section "{section.code}" is inactive but the document '
                "already exists."
            )
        if not document_type.is_active:
            if existing is None:
                raise document_error(
                    f'Document Type "{document_type.code}" is inactive.',
                    field="value",
                )
            warnings.append(
                f'Document Type "{document_type.code}" is inactive but the '
                "document already exists."
            )
        return department, section, document_type, warnings

    @staticmethod
    def _audit_values(document: Document) -> dict[str, Any]:
        return {
            "id": str(document.id),
            "companyCode": document.company_code,
            "departmentId": str(document.department_id),
            "sectionId": (
                str(document.section_id)
                if document.section_id is not None
                else None
            ),
            "documentTypeId": str(document.document_type_id),
            "documentNumber": document.document_number,
            "baseDocumentCode": document.base_document_code,
            "title": document.title,
            "ownerDepartmentId": (
                str(document.owner_department_id)
                if document.owner_department_id is not None
                else None
            ),
            "documentOwnerName": document.document_owner_name,
            "currentRevisionId": (
                str(document.current_revision_id)
                if document.current_revision_id is not None
                else None
            ),
            "isArchived": document.is_archived,
        }

    @staticmethod
    def _camel(value: str) -> str:
        head, *tail = value.split("_")
        return head + "".join(part.capitalize() for part in tail)
