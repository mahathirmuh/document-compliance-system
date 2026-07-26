"""Persistence operations for multilingual section aliases."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
)
from app.models.section_alias import SectionAlias
from app.models.section_definition import SectionDefinition


class SectionAliasRepository:
    """Database-only alias operations and matcher loading."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(self):
        return select(SectionAlias).options(
            joinedload(SectionAlias.section_definition).joinedload(
                SectionDefinition.profile
            )
        )

    async def get_by_id(
        self,
        alias_id: UUID,
        *,
        for_update: bool = False,
    ) -> SectionAlias | None:
        statement = self.base_statement().where(SectionAlias.id == alias_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_duplicate(
        self,
        *,
        section_definition_id: UUID,
        language_code: SectionAliasLanguageCode | str,
        normalised_alias: str,
        exclude_id: UUID | None = None,
    ) -> SectionAlias | None:
        language = (
            language_code.value
            if isinstance(language_code, SectionAliasLanguageCode)
            else language_code
        )
        statement = self.base_statement().where(
            SectionAlias.section_definition_id == section_definition_id,
            SectionAlias.language_code == language,
            SectionAlias.normalised_alias == normalised_alias,
        )
        if exclude_id is not None:
            statement = statement.where(SectionAlias.id != exclude_id)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add(self, alias: SectionAlias) -> SectionAlias:
        self.session.add(alias)
        await self.session.flush()
        return alias

    async def add_many(
        self,
        aliases: Sequence[SectionAlias],
        *,
        batch_size: int = 1000,
    ) -> list[SectionAlias]:
        items = list(aliases)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_active_for_profile(
        self,
        profile_id: UUID,
        *,
        language_code: SectionAliasLanguageCode | None = None,
    ) -> list[SectionAlias]:
        statement = self.base_statement().join(
            SectionDefinition,
            SectionDefinition.id == SectionAlias.section_definition_id,
        ).where(
            SectionDefinition.profile_id == profile_id,
            SectionDefinition.is_active.is_(True),
            SectionAlias.is_active.is_(True),
        )
        if language_code is not None:
            statement = statement.where(
                SectionAlias.language_code.in_(
                    [language_code, SectionAliasLanguageCode.ANY]
                )
            )
        result = await self.session.scalars(
            statement.order_by(
                desc(SectionAlias.priority),
                asc(SectionDefinition.display_order),
                asc(SectionAlias.id),
            )
        )
        return list(result.unique().all())

    async def list_page(
        self,
        *,
        profile_id: UUID | None = None,
        section_definition_id: UUID | None = None,
        language_code: SectionAliasLanguageCode | None = None,
        match_type: SectionAliasMatchType | None = None,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "priority",
        sort_order: str = "desc",
    ) -> tuple[list[SectionAlias], int]:
        statement = self.base_statement().join(
            SectionDefinition,
            SectionDefinition.id == SectionAlias.section_definition_id,
        )
        if profile_id is not None:
            statement = statement.where(
                SectionDefinition.profile_id == profile_id
            )
        if section_definition_id is not None:
            statement = statement.where(
                SectionAlias.section_definition_id
                == section_definition_id
            )
        if language_code is not None:
            statement = statement.where(
                SectionAlias.language_code == language_code
            )
        if match_type is not None:
            statement = statement.where(
                SectionAlias.match_type == match_type
            )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    SectionAlias.alias_text.ilike(pattern),
                    SectionAlias.normalised_alias.ilike(pattern),
                    SectionDefinition.canonical_code.ilike(pattern),
                )
            )
        if is_active is not None:
            statement = statement.where(
                SectionAlias.is_active.is_(is_active)
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
            "aliasText": SectionAlias.alias_text,
            "languageCode": SectionAlias.language_code,
            "matchType": SectionAlias.match_type,
            "priority": SectionAlias.priority,
            "isActive": SectionAlias.is_active,
            "createdAt": SectionAlias.created_at,
            "updatedAt": SectionAlias.updated_at,
        }
        column = columns.get(sort_by, SectionAlias.priority)
        ordering = desc(column) if sort_order == "desc" else asc(column)
        result = await self.session.scalars(
            statement.order_by(ordering, asc(SectionAlias.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
