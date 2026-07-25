"""Document-status persistence operations."""

from uuid import UUID

from sqlalchemy import select

from app.models.document_status import DocumentStatus
from app.repositories.master_data_base import BaseMasterDataRepository


class DocumentStatusRepository(BaseMasterDataRepository[DocumentStatus]):
    model = DocumentStatus
    sortable_columns = {
        "code": DocumentStatus.code,
        "name": DocumentStatus.name,
        "displayOrder": DocumentStatus.display_order,
        "isActive": DocumentStatus.is_active,
        "createdAt": DocumentStatus.created_at,
        "updatedAt": DocumentStatus.updated_at,
    }

    async def get_initial(
        self,
        *,
        exclude_id: UUID | None = None,
        for_update: bool = False,
    ) -> DocumentStatus | None:
        statement = select(DocumentStatus).where(
            DocumentStatus.is_initial.is_(True),
            DocumentStatus.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(DocumentStatus.id != exclude_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

