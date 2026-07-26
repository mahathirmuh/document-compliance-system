"""Section persistence operations."""

from typing import Any, ClassVar, Unpack
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from app.models.section import Section
from app.repositories.master_data_base import (
    BaseMasterDataRepository,
    MasterDataListPageFilters,
)


class SectionRepository(BaseMasterDataRepository[Section]):
    model = Section
    sortable_columns: ClassVar[dict[str, InstrumentedAttribute[Any]]] = {
        "code": Section.code,
        "name": Section.name,
        "departmentId": Section.department_id,
        "isActive": Section.is_active,
        "createdAt": Section.created_at,
        "updatedAt": Section.updated_at,
    }

    def base_statement(self) -> Select[tuple[Section]]:
        return (
            select(Section)
            .options(selectinload(Section.department))
            .where(Section.deleted_at.is_(None))
        )

    async def get_by_department_and_code(
        self,
        department_id: UUID,
        code: str,
        *,
        for_update: bool = False,
    ) -> Section | None:
        statement = self.base_statement().where(
            Section.department_id == department_id,
            Section.code == code.strip().upper(),
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_id: UUID | None = None,
        statement: Select[tuple[Section]] | None = None,
        **kwargs: Unpack[MasterDataListPageFilters],
    ) -> tuple[list[Section], int]:
        statement = statement if statement is not None else self.base_statement()
        if department_id is not None:
            statement = statement.where(
                Section.department_id == department_id
            )
        return await super().list_page(statement=statement, **kwargs)

    async def options(
        self,
        *,
        department_id: UUID | None = None,
        active_only: bool = True,
        limit: int = 1000,
        statement: Select[tuple[Section]] | None = None,
    ) -> list[Section]:
        statement = statement if statement is not None else self.base_statement()
        if department_id is not None:
            statement = statement.where(
                Section.department_id == department_id
            )
        return await super().options(
            active_only=active_only,
            limit=limit,
            statement=statement,
        )
