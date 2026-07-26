"""Persistence operations for canonical section definitions."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.section_definition import SectionDefinition


class SectionDefinitionRepository:
    """Database-only canonical section operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(self):
        return select(SectionDefinition).options(
            selectinload(SectionDefinition.profile),
            selectinload(SectionDefinition.aliases),
        )

    async def get_by_id(
        self,
        definition_id: UUID,
        *,
        for_update: bool = False,
    ) -> SectionDefinition | None:
        statement = self.base_statement().where(
            SectionDefinition.id == definition_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_profile_and_code(
        self,
        profile_id: UUID,
        canonical_code: str,
        *,
        for_update: bool = False,
    ) -> SectionDefinition | None:
        statement = self.base_statement().where(
            SectionDefinition.profile_id == profile_id,
            SectionDefinition.canonical_code
            == canonical_code.strip().upper(),
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add(
        self,
        definition: SectionDefinition,
    ) -> SectionDefinition:
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def add_many(
        self,
        definitions: Sequence[SectionDefinition],
        *,
        batch_size: int = 1000,
    ) -> list[SectionDefinition]:
        items = list(definitions)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_for_profile(
        self,
        profile_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[SectionDefinition]:
        statement = self.base_statement().where(
            SectionDefinition.profile_id == profile_id
        )
        if active_only:
            statement = statement.where(
                SectionDefinition.is_active.is_(True)
            )
        result = await self.session.scalars(
            statement.order_by(
                asc(SectionDefinition.display_order),
                asc(SectionDefinition.canonical_code),
            )
        )
        return list(result.unique().all())

    async def list_page(
        self,
        *,
        profile_id: UUID | None = None,
        search: str | None = None,
        is_active: bool | None = None,
        is_required_default: bool | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "displayOrder",
        sort_order: str = "asc",
    ) -> tuple[list[SectionDefinition], int]:
        statement = self.base_statement()
        if profile_id is not None:
            statement = statement.where(
                SectionDefinition.profile_id == profile_id
            )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    SectionDefinition.canonical_code.ilike(pattern),
                    SectionDefinition.display_name.ilike(pattern),
                )
            )
        if is_active is not None:
            statement = statement.where(
                SectionDefinition.is_active.is_(is_active)
            )
        if is_required_default is not None:
            statement = statement.where(
                SectionDefinition.is_required_default.is_(
                    is_required_default
                )
            )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        columns = {
            "canonicalCode": SectionDefinition.canonical_code,
            "displayName": SectionDefinition.display_name,
            "displayOrder": SectionDefinition.display_order,
            "isRequiredDefault": SectionDefinition.is_required_default,
            "isRepeatable": SectionDefinition.is_repeatable,
            "isActive": SectionDefinition.is_active,
            "createdAt": SectionDefinition.created_at,
            "updatedAt": SectionDefinition.updated_at,
        }
        column = columns.get(sort_by, SectionDefinition.display_order)
        ordering = desc(column) if sort_order == "desc" else asc(column)
        result = await self.session.scalars(
            statement.order_by(
                ordering,
                asc(SectionDefinition.canonical_code),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
