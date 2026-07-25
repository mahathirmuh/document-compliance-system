"""Reusable persistence primitives for master-data repositories."""

from collections.abc import Mapping
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseMasterDataRepository(Generic[ModelT]):
    """Common database-only operations for soft-deletable master data."""

    model: type[ModelT]
    sortable_columns: Mapping[str, InstrumentedAttribute[Any]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(self) -> Select[tuple[ModelT]]:
        return select(self.model).where(self.model.deleted_at.is_(None))

    async def get_by_id(
        self,
        entity_id: UUID,
        *,
        for_update: bool = False,
    ) -> ModelT | None:
        statement = self.base_statement().where(self.model.id == entity_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> ModelT | None:
        statement = select(self.model).where(
            self.model.code == code.strip().upper()
        )
        if not include_deleted:
            statement = statement.where(self.model.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    def apply_filters(
        self,
        statement: Select[tuple[ModelT]],
        *,
        search: str | None,
        is_active: bool | None,
    ) -> Select[tuple[ModelT]]:
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    self.model.code.ilike(pattern),
                    self.model.name.ilike(pattern),
                )
            )
        if is_active is not None:
            statement = statement.where(
                self.model.is_active.is_(is_active)
            )
        return statement

    async def list_page(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "code",
        sort_order: str = "asc",
        statement: Select[tuple[ModelT]] | None = None,
    ) -> tuple[list[ModelT], int]:
        filtered = self.apply_filters(
            statement if statement is not None else self.base_statement(),
            search=search,
            is_active=is_active,
        )
        count_statement = select(func.count()).select_from(
            filtered.order_by(None).subquery()
        )
        total = int((await self.session.scalar(count_statement)) or 0)
        sort_column = self.sortable_columns.get(
            sort_by,
            self.sortable_columns["code"],
        )
        ordering = desc(sort_column) if sort_order == "desc" else asc(sort_column)
        result = await self.session.scalars(
            filtered.order_by(ordering, asc(self.model.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def options(
        self,
        *,
        active_only: bool = True,
        limit: int = 1000,
        statement: Select[tuple[ModelT]] | None = None,
    ) -> list[ModelT]:
        query = statement if statement is not None else self.base_statement()
        if active_only:
            query = query.where(self.model.is_active.is_(True))
        result = await self.session.scalars(
            query.order_by(asc(self.model.code)).limit(limit)
        )
        return list(result.unique().all())

    async def counts(self) -> tuple[int, int, int]:
        statement = select(
            func.count(self.model.id),
            func.count(self.model.id).filter(
                self.model.is_active.is_(True)
            ),
            func.count(self.model.id).filter(
                self.model.is_active.is_(False)
            ),
        ).where(self.model.deleted_at.is_(None))
        row = (await self.session.execute(statement)).one()
        return int(row[0]), int(row[1]), int(row[2])

