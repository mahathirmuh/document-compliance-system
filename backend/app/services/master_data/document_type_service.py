"""Document-type business rules and audited transactions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.document_type import DocumentType
from app.models.user import User
from app.repositories.document_type_repository import DocumentTypeRepository
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.document_type import (
    DocumentTypeCreate,
    DocumentTypeListResponse,
    DocumentTypeResponse,
    DocumentTypeUpdate,
)
from app.schemas.master_data import MasterDataOption
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)


class DocumentTypeService(MasterDataServiceBase):
    entity_name = "Document Type"
    entity_type = "document_type"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = DocumentTypeRepository(session)
        self.validation_rules = ValidationRuleRepository(session)

    @staticmethod
    def response(entity: DocumentType) -> DocumentTypeResponse:
        default_rule = (
            MasterDataOption.model_validate(entity.default_validation_rule)
            if entity.default_validation_rule is not None
            else None
        )
        return DocumentTypeResponse(
            id=entity.id,
            code=entity.code,
            name=entity.name,
            category=entity.category,
            description=entity.description,
            requires_section=entity.requires_section,
            default_validation_rule_id=entity.default_validation_rule_id,
            default_validation_rule=default_rule,
            is_active=entity.is_active,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def _validate_default_rule(
        self,
        rule_id: UUID | None,
        *,
        document_type_id: UUID | None,
    ) -> None:
        if rule_id is None:
            return
        rule = await self.validation_rules.get_by_id(rule_id)
        if rule is None:
            raise business_error(
                "Default validation rule was not found.",
                field="defaultValidationRuleId",
            )
        if not rule.is_active:
            raise business_error(
                "Default validation rule must be active.",
                field="defaultValidationRuleId",
            )
        if (
            rule.document_type_id is not None
            and rule.document_type_id != document_type_id
        ):
            raise business_error(
                "Default validation rule is not applicable to this document type.",
                field="defaultValidationRuleId",
            )

    async def list(
        self,
        *,
        search: str | None,
        category: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> DocumentTypeListResponse:
        items, total = await self.repository.list_page(
            search=search,
            category=category,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return DocumentTypeListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def get(self, entity_id: UUID) -> DocumentTypeResponse:
        entity = await self.repository.get_by_id(entity_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def options(self, *, active_only: bool = True) -> list[MasterDataOption]:
        entities = await self.repository.options(active_only=active_only)
        return [
            MasterDataOption.model_validate(entity) for entity in entities
        ]

    async def create(
        self,
        payload: DocumentTypeCreate,
    ) -> DocumentTypeResponse:
        if await self.repository.get_by_code(payload.code) is not None:
            raise conflict(
                "Document type code already exists.",
                field="code",
                title="Document Type could not be created.",
            )
        await self._validate_default_rule(
            payload.default_validation_rule_id,
            document_type_id=None,
        )
        values = payload.model_dump(by_alias=False)
        category = values.get("category")
        if category is not None:
            values["category"] = category.value
        entity = DocumentType(
            **values,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.repository.add(entity)
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Document type code already exists.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_DOCUMENT_TYPE,
            entity_id=entity.id,
            description=f"Document type {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message="Document type code already exists.",
        )
        return response

    async def update(
        self,
        entity_id: UUID,
        payload: DocumentTypeUpdate,
    ) -> DocumentTypeResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        values = payload.model_dump(exclude_unset=True, by_alias=False)
        if (
            "is_active" in values
            and values["is_active"] != entity.is_active
        ):
            raise business_error(
                "Use the dedicated activate or deactivate endpoint to "
                "change document type status.",
                field="isActive",
            )
        new_code = values.get("code")
        if new_code is not None and new_code != entity.code:
            duplicate = await self.repository.get_by_code(str(new_code))
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Document type code already exists.",
                    field="code",
                    title="Document Type could not be updated.",
                )
        if "default_validation_rule_id" in values:
            await self._validate_default_rule(
                values["default_validation_rule_id"],
                document_type_id=entity.id,
            )
        category = values.get("category")
        if category is not None:
            values["category"] = category.value
        for key, value in values.items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Document type code already exists.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_DOCUMENT_TYPE,
            entity_id=entity.id,
            description=f"Document type {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Document type code already exists.",
        )
        return response

    async def set_active(
        self,
        entity_id: UUID,
        *,
        active: bool,
    ) -> DocumentTypeResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        entity.is_active = active
        entity.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(entity, attribute_names=["updated_at"])
        response = self.response(entity)
        await self.commit_audited(
            action=(
                AuditAction.ACTIVATE_DOCUMENT_TYPE
                if active
                else AuditAction.DEACTIVATE_DOCUMENT_TYPE
            ),
            entity_id=entity.id,
            description=(
                f"Document type {entity.code} was "
                f"{'activated' if active else 'deactivated'}."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Document type state could not be changed.",
            duplicate_field=None,
        )
        return response
