"""Document-type persistence operations."""

from typing import Any, ClassVar

from sqlalchemy import Select, select
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from app.models.document_type import DocumentType
from app.repositories.master_data_base import BaseMasterDataRepository


class DocumentTypeRepository(BaseMasterDataRepository[DocumentType]):
    model = DocumentType
    sortable_columns: ClassVar[
        dict[str, InstrumentedAttribute[Any]]
    ] = {
        "code": DocumentType.code,
        "name": DocumentType.name,
        "category": DocumentType.category,
        "isActive": DocumentType.is_active,
        "createdAt": DocumentType.created_at,
        "updatedAt": DocumentType.updated_at,
    }

    def base_statement(self) -> Select[tuple[DocumentType]]:
        return (
            select(DocumentType)
            .options(selectinload(DocumentType.default_validation_rule))
            .where(DocumentType.deleted_at.is_(None))
        )

    async def list_page(
        self,
        *,
        category: str | None = None,
        **kwargs: object,
    ) -> tuple[list[DocumentType], int]:
        statement = self.base_statement()
        if category is not None:
            statement = statement.where(DocumentType.category == category)
        return await super().list_page(statement=statement, **kwargs)
