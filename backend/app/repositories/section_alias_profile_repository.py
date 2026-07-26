"""Persistence operations for section-alias profiles."""

from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.section_alias_profile import SectionAliasProfile
from app.models.section_definition import SectionDefinition


class SectionAliasProfileRepository:
    """Database-only operations for alias profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(self):
        return select(SectionAliasProfile).options(
            selectinload(SectionAliasProfile.definitions).selectinload(
                SectionDefinition.aliases
            )
        )

    async def get_by_id(
        self,
        profile_id: UUID,
        *,
        for_update: bool = False,
    ) -> SectionAliasProfile | None:
        statement = self.base_statement().where(
            SectionAliasProfile.id == profile_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        *,
        for_update: bool = False,
    ) -> SectionAliasProfile | None:
        statement = self.base_statement().where(
            SectionAliasProfile.code == code.strip().upper()
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_default(
        self,
        *,
        for_update: bool = False,
    ) -> SectionAliasProfile | None:
        statement = self.base_statement().where(
            SectionAliasProfile.is_default.is_(True)
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add(
        self,
        profile: SectionAliasProfile,
    ) -> SectionAliasProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def list_page(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[list[SectionAliasProfile], int]:
        statement = self.base_statement()
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    SectionAliasProfile.code.ilike(pattern),
                    SectionAliasProfile.name.ilike(pattern),
                )
            )
        if is_active is not None:
            statement = statement.where(
                SectionAliasProfile.is_active.is_(is_active)
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
            "code": SectionAliasProfile.code,
            "name": SectionAliasProfile.name,
            "isDefault": SectionAliasProfile.is_default,
            "isActive": SectionAliasProfile.is_active,
            "createdAt": SectionAliasProfile.created_at,
            "updatedAt": SectionAliasProfile.updated_at,
        }
        column = columns.get(sort_by, SectionAliasProfile.code)
        ordering = desc(column) if sort_order == "desc" else asc(column)
        result = await self.session.scalars(
            statement.order_by(ordering, asc(SectionAliasProfile.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
