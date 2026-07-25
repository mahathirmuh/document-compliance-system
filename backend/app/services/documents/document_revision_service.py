"""Transactional document revision management."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.schemas.document_revision import (
    DocumentRevisionCreate,
    DocumentRevisionListItem,
    DocumentRevisionResponse,
    DocumentRevisionSetCurrentRequest,
    DocumentRevisionSupersedeRequest,
    DocumentRevisionUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
    document_not_found,
    revision_list_item,
    revision_not_found,
    revision_response,
)
from app.services.documents.document_code_service import DocumentCodeService
from app.utils.datetime import utc_now


class DocumentRevisionService(DocumentServiceBase):
    """Own revision creation, updates, current selection, and superseding."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)
        self.codes = DocumentCodeService()

    async def list(
        self,
        document_id: UUID,
    ) -> list[DocumentRevisionListItem]:
        document = await self._document(document_id)
        revisions = await self.revisions.list_by_document(document.id)
        return [revision_list_item(revision) for revision in revisions]

    async def get(
        self,
        document_id: UUID,
        revision_id: UUID,
    ) -> DocumentRevisionResponse:
        await self._document(document_id)
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document_id,
        )
        if revision is None:
            raise revision_not_found()
        return revision_response(revision)

    async def create(
        self,
        document_id: UUID,
        payload: DocumentRevisionCreate,
        *,
        commit: bool = True,
    ) -> DocumentRevisionResponse:
        document = await self._document(document_id, for_update=True)
        if document.is_archived:
            raise document_error(
                "Archived documents cannot receive new revisions."
            )
        revision_code = self.codes.normalize_revision_code(
            payload.revision_code
        )
        existing = await self.revisions.get_by_document_and_code(
            document.id,
            revision_code,
            for_update=True,
        )
        if existing is not None:
            raise document_conflict(
                f"Revision {revision_code} already exists for this document.",
                field="revisionCode",
                title="Document revision could not be created.",
            )
        status = await self.resolve_status(payload.document_status_id)
        rule = await self.resolve_validation_rule(
            document.document_type,
            payload.validation_rule_id,
        )
        full_code = self.codes.generate_full_document_code(
            document.base_document_code,
            revision_code,
        )
        if await self.revisions.exists_by_full_code(full_code):
            raise document_conflict(
                f"Revision code {full_code} already exists.",
                field="revisionCode",
                title="Document revision could not be created.",
            )
        revision = DocumentRevision(
            document_id=document.id,
            revision_code=revision_code,
            revision_number=self.codes.revision_number(revision_code),
            full_document_code=full_code,
            document_status_id=status.id,
            validation_rule_id=rule.id if rule is not None else None,
            issue_date=payload.issue_date,
            effective_date=payload.effective_date,
            review_date=payload.review_date,
            expiry_date=payload.expiry_date,
            sharepoint_url=payload.sharepoint_url,
            external_reference=payload.external_reference,
            remarks=payload.remarks,
            is_current=False,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.revisions.create(revision)
            if (
                payload.set_as_current
                or document.current_revision_id is None
            ):
                await self.revisions.set_current(revision)
                document.current_revision_id = revision.id
            document.updated_by = self.user.id
            await self.session.flush()
            await self.audit(
                action=AuditAction.CREATE_DOCUMENT_REVISION,
                entity_type="document_revision",
                entity_id=revision.id,
                description=f"Created revision {full_code}.",
                new_values=self._audit_values(document, revision),
            )
            if commit:
                await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                f"Revision {revision_code} already exists for this document.",
                field="revisionCode",
                title="Document revision could not be created.",
            ) from exc
        result = await self.revisions.get_by_id(
            revision.id,
            document_id=document.id,
        )
        assert result is not None
        return revision_response(result)

    async def update(
        self,
        document_id: UUID,
        revision_id: UUID,
        payload: DocumentRevisionUpdate,
    ) -> DocumentRevisionResponse:
        document = await self._document(document_id, for_update=True)
        if document.is_archived:
            raise document_error(
                "Archived document revisions are read-only."
            )
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
            for_update=True,
        )
        if revision is None:
            raise revision_not_found()
        changes = payload.model_dump(
            by_alias=False,
            exclude_unset=True,
        )
        reason = changes.pop("change_reason", None)
        old_values = self._audit_values(document, revision)
        if "revision_code" in changes:
            if changes["revision_code"] is None:
                raise document_error(
                    "revisionCode cannot be null.",
                    field="revisionCode",
                )
            revision_code = self.codes.normalize_revision_code(
                changes["revision_code"]
            )
            if revision_code != revision.revision_code:
                if not reason:
                    raise document_error(
                        "changeReason is required when changing revisionCode.",
                        field="changeReason",
                    )
                duplicate = await self.revisions.get_by_document_and_code(
                    document.id,
                    revision_code,
                    for_update=True,
                )
                if duplicate is not None and duplicate.id != revision.id:
                    raise document_conflict(
                        f"Revision {revision_code} already exists.",
                        field="revisionCode",
                    )
                full_code = self.codes.generate_full_document_code(
                    document.base_document_code,
                    revision_code,
                )
                if await self.revisions.exists_by_full_code(
                    full_code,
                    exclude_id=revision.id,
                ):
                    raise document_conflict(
                        f"Revision code {full_code} already exists.",
                        field="revisionCode",
                    )
                revision.revision_code = revision_code
                revision.revision_number = self.codes.revision_number(
                    revision_code
                )
                revision.full_document_code = full_code
        if "document_status_id" in changes:
            if changes["document_status_id"] is None:
                raise document_error(
                    "documentStatusId cannot be null.",
                    field="documentStatusId",
                )
            if (
                changes["document_status_id"]
                != revision.document_status_id
            ):
                status = await self.resolve_status(
                    changes["document_status_id"]
                )
                revision.document_status_id = status.id
                revision.document_status = status
        if (
            "validation_rule_id" in changes
            and changes["validation_rule_id"]
            != revision.validation_rule_id
        ):
            requested_rule_id = changes["validation_rule_id"]
            rule = (
                await self.resolve_validation_rule(
                    document.document_type,
                    requested_rule_id,
                )
                if requested_rule_id is not None
                else None
            )
            revision.validation_rule_id = requested_rule_id
            revision.validation_rule = rule
        for field in (
            "issue_date",
            "effective_date",
            "review_date",
            "expiry_date",
            "sharepoint_url",
            "external_reference",
            "remarks",
        ):
            if field in changes:
                setattr(revision, field, changes[field])
        self._validate_dates(
            issue_date=revision.issue_date,
            effective_date=revision.effective_date,
            review_date=revision.review_date,
            expiry_date=revision.expiry_date,
        )
        revision.updated_by = self.user.id
        document.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.audit(
                action=AuditAction.UPDATE_DOCUMENT_REVISION,
                entity_type="document_revision",
                entity_id=revision.id,
                description=(
                    f"Updated revision {revision.full_document_code}."
                ),
                old_values=old_values,
                new_values={
                    **self._audit_values(document, revision),
                    "reason": reason,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise document_conflict(
                "The requested revision code already exists.",
                field="revisionCode",
                title="Document revision could not be saved.",
            ) from exc
        result = await self.revisions.get_by_id(
            revision.id,
            document_id=document.id,
        )
        assert result is not None
        return revision_response(result)

    async def set_current(
        self,
        document_id: UUID,
        revision_id: UUID,
        payload: DocumentRevisionSetCurrentRequest | None,
    ) -> DocumentRevisionResponse:
        document = await self._document(document_id, for_update=True)
        if document.is_archived:
            raise document_error(
                "Archived document revisions cannot be changed."
            )
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
            for_update=True,
        )
        if revision is None:
            raise revision_not_found()
        if revision.is_superseded:
            raise document_error(
                "A superseded revision cannot be selected as current.",
                field="revisionId",
            )
        old_revision_id = document.current_revision_id
        await self.revisions.set_current(revision)
        document.current_revision_id = revision.id
        document.updated_by = self.user.id
        await self.session.flush()
        await self.audit(
            action=AuditAction.SET_CURRENT_REVISION,
            entity_type="document_revision",
            entity_id=revision.id,
            description=f"Set {revision.full_document_code} as current.",
            old_values={
                "documentId": str(document.id),
                "currentRevisionId": (
                    str(old_revision_id)
                    if old_revision_id is not None
                    else None
                ),
            },
            new_values={
                **self._audit_values(document, revision),
                "reason": payload.reason if payload is not None else None,
            },
        )
        await self.session.commit()
        result = await self.revisions.get_by_id(
            revision.id,
            document_id=document.id,
        )
        assert result is not None
        return revision_response(result)

    async def supersede(
        self,
        document_id: UUID,
        revision_id: UUID,
        payload: DocumentRevisionSupersedeRequest,
    ) -> DocumentRevisionResponse:
        document = await self._document(document_id, for_update=True)
        if document.is_archived:
            raise document_error(
                "Archived document revisions cannot be changed."
            )
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
            for_update=True,
        )
        replacement = await self.revisions.get_by_id(
            payload.superseded_by_revision_id,
            document_id=document.id,
            for_update=True,
        )
        if revision is None:
            raise revision_not_found()
        if replacement is None:
            raise document_error(
                "Replacement revision was not found in this document.",
                field="supersededByRevisionId",
            )
        if revision.id == replacement.id:
            raise document_error(
                "A revision cannot supersede itself.",
                field="supersededByRevisionId",
            )
        if revision.is_superseded:
            raise document_conflict(
                "Document revision is already superseded.",
                field="revisionId",
                title="Document revision could not be superseded.",
            )
        if replacement.is_superseded:
            raise document_error(
                "The replacement revision is already superseded.",
                field="supersededByRevisionId",
            )
        old_values = self._audit_values(document, revision)
        await self.revisions.mark_superseded(
            revision,
            superseded_at=utc_now(),
            superseded_by_revision_id=replacement.id,
        )
        superseded_status = await self.document_statuses.get_by_code(
            "SUPERSEDED"
        )
        if superseded_status is not None and superseded_status.is_active:
            revision.document_status_id = superseded_status.id
            revision.document_status = superseded_status
        if revision.is_current or document.current_revision_id == revision.id:
            await self.revisions.set_current(replacement)
            document.current_revision_id = replacement.id
        revision.updated_by = self.user.id
        replacement.updated_by = self.user.id
        document.updated_by = self.user.id
        await self.session.flush()
        await self.audit(
            action=AuditAction.SUPERSEDE_DOCUMENT_REVISION,
            entity_type="document_revision",
            entity_id=revision.id,
            description=(
                f"Superseded {revision.full_document_code} with "
                f"{replacement.full_document_code}."
            ),
            old_values=old_values,
            new_values={
                **self._audit_values(document, revision),
                "supersededByRevisionId": str(replacement.id),
                "reason": payload.reason,
            },
        )
        await self.session.commit()
        result = await self.revisions.get_by_id(
            revision.id,
            document_id=document.id,
        )
        assert result is not None
        return revision_response(result)

    async def _document(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
    ) -> Document:
        document = await self.documents.get_detail(
            document_id,
            for_update=for_update,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        return document

    @staticmethod
    def _validate_dates(
        *,
        issue_date: date | None,
        effective_date: date | None,
        review_date: date | None,
        expiry_date: date | None,
    ) -> None:
        if (
            effective_date is not None
            and expiry_date is not None
            and expiry_date < effective_date
        ):
            raise document_error(
                "expiryDate must not be before effectiveDate.",
                field="expiryDate",
            )
        if (
            issue_date is not None
            and review_date is not None
            and review_date < issue_date
        ):
            raise document_error(
                "reviewDate must not be before issueDate.",
                field="reviewDate",
            )

    @staticmethod
    def _audit_values(
        document: Document,
        revision: DocumentRevision,
    ) -> dict[str, Any]:
        return {
            "documentId": str(document.id),
            "baseDocumentCode": document.base_document_code,
            "revisionId": str(revision.id),
            "revisionCode": revision.revision_code,
            "fullDocumentCode": revision.full_document_code,
            "documentStatusId": str(revision.document_status_id),
            "validationRuleId": (
                str(revision.validation_rule_id)
                if revision.validation_rule_id is not None
                else None
            ),
            "isCurrent": revision.is_current,
            "isSuperseded": revision.is_superseded,
        }
