"""Validation-rule persistence operations."""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.models.validation_rule import ValidationRule
from app.repositories.master_data_base import BaseMasterDataRepository


class ValidationRuleRepository(BaseMasterDataRepository[ValidationRule]):
    model = ValidationRule
    sortable_columns = {
        "code": ValidationRule.code,
        "name": ValidationRule.name,
        "documentTypeId": ValidationRule.document_type_id,
        "isDefault": ValidationRule.is_default,
        "isActive": ValidationRule.is_active,
        "createdAt": ValidationRule.created_at,
        "updatedAt": ValidationRule.updated_at,
    }

    def base_statement(self) -> Select[tuple[ValidationRule]]:
        return (
            select(ValidationRule)
            .options(selectinload(ValidationRule.document_type))
            .where(ValidationRule.deleted_at.is_(None))
        )

    async def get_default(
        self,
        document_type_id: UUID | None,
        *,
        exclude_id: UUID | None = None,
        for_update: bool = False,
    ) -> ValidationRule | None:
        statement = self.base_statement().where(
            ValidationRule.is_default.is_(True)
        )
        if document_type_id is None:
            statement = statement.where(
                ValidationRule.document_type_id.is_(None)
            )
        else:
            statement = statement.where(
                ValidationRule.document_type_id == document_type_id
            )
        if exclude_id is not None:
            statement = statement.where(ValidationRule.id != exclude_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        document_type_id: UUID | None = None,
        is_default: bool | None = None,
        **kwargs: object,
    ) -> tuple[list[ValidationRule], int]:
        statement = self.base_statement()
        if document_type_id is not None:
            statement = statement.where(
                ValidationRule.document_type_id == document_type_id
            )
        if is_default is not None:
            statement = statement.where(
                ValidationRule.is_default.is_(is_default)
            )
        return await super().list_page(statement=statement, **kwargs)

