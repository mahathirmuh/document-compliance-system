"""Database-only access for scoped glossary profiles."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.glossary_enums import GlossaryScopeType
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_translation import GlossaryTranslation


class GlossaryProfileRepository:
    """Persistence queries without glossary business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(GlossaryProfile).options(
            selectinload(GlossaryProfile.terms).selectinload(
                GlossaryTerm.translations
            ).selectinload(GlossaryTranslation.variants)
        )

    async def add(self, profile: GlossaryProfile) -> GlossaryProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_by_id(
        self,
        profile_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryProfile | None:
        statement = self.base_statement().where(
            GlossaryProfile.id == profile_id
        )
        statement = self._scope_to_departments(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryProfile
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        *,
        for_update: bool = False,
    ) -> GlossaryProfile | None:
        statement = self.base_statement().where(
            GlossaryProfile.code == code.strip().upper()
        )
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryProfile
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        scope_type: GlossaryScopeType | None = None,
        department_id: UUID | None = None,
        document_type_id: UUID | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[list[GlossaryProfile], int]:
        statement = self.base_statement()
        statement = self._scope_to_departments(statement, department_ids)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    GlossaryProfile.code.ilike(pattern),
                    GlossaryProfile.name.ilike(pattern),
                    GlossaryProfile.description.ilike(pattern),
                )
            )
        if scope_type is not None:
            statement = statement.where(
                GlossaryProfile.scope_type == scope_type
            )
        if department_id is not None:
            statement = statement.where(
                GlossaryProfile.department_id == department_id
            )
        if document_type_id is not None:
            statement = statement.where(
                GlossaryProfile.document_type_id == document_type_id
            )
        if is_active is not None:
            statement = statement.where(
                GlossaryProfile.is_active.is_(is_active)
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
        sort_columns = {
            "code": GlossaryProfile.code,
            "name": GlossaryProfile.name,
            "scopeType": GlossaryProfile.scope_type,
            "updatedAt": GlossaryProfile.updated_at,
        }
        sort_column = sort_columns.get(sort_by, GlossaryProfile.code)
        order = asc(sort_column) if sort_order == "asc" else desc(sort_column)
        result = await self.session.scalars(
            statement.order_by(order, GlossaryProfile.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def list_by_ids(
        self,
        profile_ids: Sequence[UUID],
        *,
        department_ids: Sequence[UUID] | None = None,
        active_only: bool = True,
    ) -> list[GlossaryProfile]:
        if not profile_ids:
            return []
        statement = self.base_statement().where(
            GlossaryProfile.id.in_(list(profile_ids))
        )
        statement = self._scope_to_departments(statement, department_ids)
        if active_only:
            statement = statement.where(GlossaryProfile.is_active.is_(True))
        result = await self.session.scalars(
            statement.order_by(GlossaryProfile.code)
        )
        by_id = {item.id: item for item in result.unique().all()}
        return [
            by_id[profile_id]
            for profile_id in profile_ids
            if profile_id in by_id
        ]

    async def resolve_for_scope(
        self,
        *,
        department_id: UUID | None,
        document_type_id: UUID | None,
        defaults_only: bool = True,
    ) -> list[GlossaryProfile]:
        conditions = [
            and_(
                GlossaryProfile.scope_type == GlossaryScopeType.GLOBAL,
                GlossaryProfile.department_id.is_(None),
                GlossaryProfile.document_type_id.is_(None),
            )
        ]
        if department_id is not None:
            conditions.append(
                and_(
                    GlossaryProfile.scope_type
                    == GlossaryScopeType.DEPARTMENT,
                    GlossaryProfile.department_id == department_id,
                    GlossaryProfile.document_type_id.is_(None),
                )
            )
        if document_type_id is not None:
            conditions.append(
                and_(
                    GlossaryProfile.scope_type
                    == GlossaryScopeType.DOCUMENT_TYPE,
                    GlossaryProfile.department_id.is_(None),
                    GlossaryProfile.document_type_id == document_type_id,
                )
            )
        if department_id is not None and document_type_id is not None:
            conditions.append(
                and_(
                    GlossaryProfile.scope_type
                    == GlossaryScopeType.DEPARTMENT_DOCUMENT_TYPE,
                    GlossaryProfile.department_id == department_id,
                    GlossaryProfile.document_type_id == document_type_id,
                )
            )
        statement = self.base_statement().where(
            GlossaryProfile.is_active.is_(True),
            or_(*conditions),
        )
        if defaults_only:
            statement = statement.where(
                GlossaryProfile.is_default.is_(True)
            )
        result = await self.session.scalars(statement)
        priority = {
            GlossaryScopeType.DEPARTMENT_DOCUMENT_TYPE: 4,
            GlossaryScopeType.DOCUMENT_TYPE: 3,
            GlossaryScopeType.DEPARTMENT: 2,
            GlossaryScopeType.GLOBAL: 1,
        }
        return sorted(
            result.unique().all(),
            key=lambda item: (-priority[item.scope_type], item.code),
        )

    async def get_default_in_scope(
        self,
        *,
        scope_type: GlossaryScopeType,
        department_id: UUID | None,
        document_type_id: UUID | None,
        exclude_id: UUID | None = None,
        for_update: bool = False,
    ) -> GlossaryProfile | None:
        statement = self.base_statement().where(
            GlossaryProfile.scope_type == scope_type,
            GlossaryProfile.department_id.is_(department_id)
            if department_id is None
            else GlossaryProfile.department_id == department_id,
            GlossaryProfile.document_type_id.is_(document_type_id)
            if document_type_id is None
            else GlossaryProfile.document_type_id == document_type_id,
            GlossaryProfile.is_default.is_(True),
            GlossaryProfile.is_active.is_(True),
        )
        if exclude_id is not None:
            statement = statement.where(GlossaryProfile.id != exclude_id)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryProfile
            ).execution_options(populate_existing=True)
        return (
            await self.session.execute(statement.limit(1))
        ).scalar_one_or_none()

    @staticmethod
    def _scope_to_departments(statement, department_ids):
        if department_ids is None:
            return statement
        allowed = list(department_ids)
        if not allowed:
            return statement.where(GlossaryProfile.department_id.is_(None))
        return statement.where(
            or_(
                GlossaryProfile.department_id.is_(None),
                GlossaryProfile.department_id.in_(allowed),
            )
        )
