"""Scope and effective-date handling for audited glossary exceptions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.department import Department
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.glossary_enums import GlossaryExceptionScopeType
from app.models.glossary_exception import GlossaryException
from app.models.section_definition import SectionDefinition
from app.models.user import User
from app.repositories.glossary_exception_repository import (
    GlossaryExceptionRepository,
)
from app.repositories.glossary_term_repository import GlossaryTermRepository
from app.schemas.glossary import (
    GlossaryExceptionCreate,
    GlossaryExceptionListResponse,
    GlossaryExceptionResponse,
    GlossaryExceptionUpdate,
    GlossaryExceptionValues,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.base import (
    GlossaryServiceBase,
    glossary_error,
    glossary_not_found,
)
from app.services.glossary.contracts import (
    GlossaryMatchCandidate,
    GlossaryValidationScope,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_SCOPE_PRIORITY = {
    GlossaryExceptionScopeType.GLOBAL: 1,
    GlossaryExceptionScopeType.DEPARTMENT: 2,
    GlossaryExceptionScopeType.DOCUMENT: 3,
    GlossaryExceptionScopeType.DOCUMENT_REVISION: 4,
    GlossaryExceptionScopeType.DOCUMENT_FILE: 5,
    GlossaryExceptionScopeType.SECTION: 6,
}


class GlossaryExceptionService:
    """Resolve exceptions without silently treating expired rows as active."""

    @staticmethod
    def is_effective(
        item: GlossaryException,
        *,
        as_of: date,
    ) -> bool:
        return (
            item.is_active
            and (
                item.effective_from is None
                or item.effective_from <= as_of
            )
            and (item.effective_to is None or item.effective_to >= as_of)
        )

    @staticmethod
    def is_expired(item: GlossaryException, *, as_of: date) -> bool:
        return bool(
            item.is_active
            and item.effective_to is not None
            and item.effective_to < as_of
        )

    def select(
        self,
        exceptions: Sequence[GlossaryException],
        *,
        term_id: object,
        exception_type: str,
        scope: GlossaryValidationScope,
        language_code: str | None = None,
        section_definition_id: object | None = None,
        as_of: date,
    ) -> tuple[GlossaryException | None, list[GlossaryException]]:
        applicable = [
            item
            for item in exceptions
            if item.glossary_term_id == term_id
            and item.exception_type.value == exception_type
            and (
                item.language_code is None
                or item.language_code.value == language_code
            )
            and self._scope_matches(
                item,
                scope,
                section_definition_id=section_definition_id,
            )
        ]
        effective = [
            item for item in applicable if self.is_effective(item, as_of=as_of)
        ]
        expired = [
            item for item in applicable if self.is_expired(item, as_of=as_of)
        ]
        effective.sort(
            key=lambda item: (
                -_SCOPE_PRIORITY[item.scope_type],
                item.created_at,
            )
        )
        return (effective[0] if effective else None), expired

    def select_for_match(
        self,
        exceptions: Sequence[GlossaryException],
        *,
        candidate: GlossaryMatchCandidate,
        exception_type: str,
        scope: GlossaryValidationScope,
        as_of: date,
    ) -> tuple[GlossaryException | None, list[GlossaryException]]:
        return self.select(
            exceptions,
            term_id=candidate.glossary_term_id,
            exception_type=exception_type,
            scope=scope,
            language_code=candidate.language_code,
            section_definition_id=candidate.section_definition_id,
            as_of=as_of,
        )

    @staticmethod
    def _scope_matches(
        item: GlossaryException,
        scope: GlossaryValidationScope,
        *,
        section_definition_id: object | None,
    ) -> bool:
        checks = {
            GlossaryExceptionScopeType.GLOBAL: True,
            GlossaryExceptionScopeType.DEPARTMENT: (
                item.department_id == scope.department_id
            ),
            GlossaryExceptionScopeType.DOCUMENT: (
                item.document_id == scope.document_id
            ),
            GlossaryExceptionScopeType.DOCUMENT_REVISION: (
                item.document_revision_id == scope.document_revision_id
            ),
            GlossaryExceptionScopeType.DOCUMENT_FILE: (
                item.document_file_id == scope.document_file_id
            ),
            GlossaryExceptionScopeType.SECTION: (
                item.section_definition_id == section_definition_id
            ),
        }
        return checks[item.scope_type]


class GlossaryExceptionManagementService(GlossaryServiceBase):
    """Create and update reasoned exceptions without hard deletion."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = GlossaryExceptionRepository(session)
        self.terms = GlossaryTermRepository(session)
        self.resolver = GlossaryExceptionService()

    def response(
        self,
        item: GlossaryException,
        *,
        as_of: date | None = None,
    ) -> GlossaryExceptionResponse:
        today = as_of or datetime.now(UTC).date()
        return GlossaryExceptionResponse(
            id=item.id,
            glossary_term_id=item.glossary_term_id,
            term_code=item.term.term_code if item.term is not None else None,
            scope_type=item.scope_type,
            department_id=item.department_id,
            document_id=item.document_id,
            document_revision_id=item.document_revision_id,
            document_file_id=item.document_file_id,
            section_definition_id=item.section_definition_id,
            language_code=item.language_code,
            exception_type=item.exception_type,
            reason=item.reason,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            is_active=item.is_active,
            is_effective=self.resolver.is_effective(item, as_of=today),
            is_expired=self.resolver.is_expired(item, as_of=today),
            approved_by=item.approved_by,
            created_by=item.created_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def list(self, **filters: object) -> GlossaryExceptionListResponse:
        page = int(filters.pop("page", 1))
        page_size = int(filters.pop("page_size", 20))
        items, total = await self.repository.list_page(
            department_ids=self.department_ids,
            page=page,
            page_size=page_size,
            **filters,
        )
        return GlossaryExceptionListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def create(
        self,
        payload: GlossaryExceptionCreate,
    ) -> GlossaryExceptionResponse:
        term = await self.terms.get_by_id(
            payload.glossary_term_id,
            department_ids=self.department_ids,
        )
        if term is None:
            raise glossary_error(
                "Glossary term was not found.",
                field="glossaryTermId",
            )
        await self._validate_scope(payload)
        item = GlossaryException(
            **payload.model_dump(by_alias=False),
            term=term,
            created_by=self.user.id,
        )
        await self.repository.add(item)
        response = self.response(item)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_EXCEPTION,
            entity_type="GlossaryException",
            entity_id=item.id,
            description="Glossary exception created.",
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.session.commit()
        return response

    async def update(
        self,
        exception_id: UUID,
        payload: GlossaryExceptionUpdate,
    ) -> GlossaryExceptionResponse:
        item = await self.repository.get_by_id(
            exception_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if item is None:
            raise glossary_not_found("Glossary exception")
        old = self.response(item)
        values = self._merged_values(item, payload)
        await self._validate_scope(values)
        for key, value in values.model_dump(by_alias=False).items():
            if key != "glossary_term_id":
                setattr(item, key, value)
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["updated_at"])
        response = self.response(item)
        await self.audit(
            action=AuditAction.UPDATE_GLOSSARY_EXCEPTION,
            entity_type="GlossaryException",
            entity_id=item.id,
            description="Glossary exception updated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.session.commit()
        return response

    async def deactivate(
        self,
        exception_id: UUID,
    ) -> GlossaryExceptionResponse:
        item = await self.repository.get_by_id(
            exception_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if item is None:
            raise glossary_not_found("Glossary exception")
        old = self.response(item)
        item.is_active = False
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["updated_at"])
        response = self.response(item)
        await self.audit(
            action=AuditAction.UPDATE_GLOSSARY_EXCEPTION,
            entity_type="GlossaryException",
            entity_id=item.id,
            description="Glossary exception deactivated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.session.commit()
        return response

    async def _validate_scope(
        self,
        values: GlossaryExceptionValues,
    ) -> None:
        if values.department_id is not None:
            department = await self.session.get(
                Department,
                values.department_id,
            )
            if department is None:
                raise glossary_error(
                    "Department was not found.",
                    field="departmentId",
                )
        document = None
        if values.document_id is not None:
            document = await self.session.get(Document, values.document_id)
            if document is None:
                raise glossary_error(
                    "Document was not found.",
                    field="documentId",
                )
        revision = None
        if values.document_revision_id is not None:
            revision = await self.session.get(
                DocumentRevision,
                values.document_revision_id,
            )
            if revision is None:
                raise glossary_error(
                    "Document revision was not found.",
                    field="documentRevisionId",
                )
        document_file = None
        if values.document_file_id is not None:
            document_file = await self.session.get(
                DocumentFile,
                values.document_file_id,
            )
            if document_file is None:
                raise glossary_error(
                    "Document file was not found.",
                    field="documentFileId",
                )
        if values.section_definition_id is not None:
            section = await self.session.get(
                SectionDefinition,
                values.section_definition_id,
            )
            if section is None:
                raise glossary_error(
                    "Section definition was not found.",
                    field="sectionDefinitionId",
                )
        if (
            document is not None
            and revision is not None
            and revision.document_id != document.id
        ):
            raise glossary_error(
                "Revision does not belong to the selected document.",
                field="documentRevisionId",
            )
        if (
            revision is not None
            and document_file is not None
            and document_file.document_revision_id != revision.id
        ):
            raise glossary_error(
                "File does not belong to the selected revision.",
                field="documentFileId",
            )

    @staticmethod
    def _merged_values(
        item: GlossaryException,
        payload: GlossaryExceptionUpdate,
    ) -> GlossaryExceptionValues:
        values = {
            "glossary_term_id": item.glossary_term_id,
            "scope_type": item.scope_type,
            "department_id": item.department_id,
            "document_id": item.document_id,
            "document_revision_id": item.document_revision_id,
            "document_file_id": item.document_file_id,
            "section_definition_id": item.section_definition_id,
            "language_code": item.language_code,
            "exception_type": item.exception_type,
            "reason": item.reason,
            "effective_from": item.effective_from,
            "effective_to": item.effective_to,
            "is_active": item.is_active,
            "approved_by": item.approved_by,
        }
        values.update(
            payload.model_dump(by_alias=False, exclude_unset=True)
        )
        return GlossaryExceptionValues.model_validate(values)
