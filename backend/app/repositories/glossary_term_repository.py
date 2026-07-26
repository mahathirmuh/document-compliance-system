"""Database-only glossary term, translation, and variant access."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryTermType,
)
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_term_variant import GlossaryTermVariant
from app.models.glossary_translation import GlossaryTranslation


class GlossaryTermRepository:
    """Persistence queries; normalization and matching remain in services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(GlossaryTerm).options(
            joinedload(GlossaryTerm.profile),
            selectinload(GlossaryTerm.translations).selectinload(
                GlossaryTranslation.variants
            ),
        )

    async def add(self, term: GlossaryTerm) -> GlossaryTerm:
        self.session.add(term)
        await self.session.flush()
        return term

    async def add_translation(
        self,
        translation: GlossaryTranslation,
    ) -> GlossaryTranslation:
        self.session.add(translation)
        await self.session.flush()
        return translation

    async def add_variant(
        self,
        variant: GlossaryTermVariant,
    ) -> GlossaryTermVariant:
        self.session.add(variant)
        await self.session.flush()
        return variant

    async def get_by_id(
        self,
        term_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryTerm | None:
        statement = self.base_statement().where(GlossaryTerm.id == term_id)
        statement = self._scope_to_departments(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryTerm
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_code(
        self,
        profile_id: UUID,
        term_code: str,
        *,
        for_update: bool = False,
    ) -> GlossaryTerm | None:
        statement = self.base_statement().where(
            GlossaryTerm.glossary_profile_id == profile_id,
            GlossaryTerm.term_code == term_code.strip().upper(),
        )
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryTerm
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_translation(
        self,
        translation_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryTranslation | None:
        statement = (
            select(GlossaryTranslation)
            .join(
                GlossaryTerm,
                GlossaryTerm.id == GlossaryTranslation.glossary_term_id,
            )
            .join(
                GlossaryProfile,
                GlossaryProfile.id == GlossaryTerm.glossary_profile_id,
            )
            .options(
                joinedload(GlossaryTranslation.term).joinedload(
                    GlossaryTerm.profile
                ),
                selectinload(GlossaryTranslation.variants),
            )
            .where(GlossaryTranslation.id == translation_id)
        )
        statement = self._profile_scope(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryTranslation
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_variant(
        self,
        variant_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryTermVariant | None:
        statement = (
            select(GlossaryTermVariant)
            .join(
                GlossaryTranslation,
                GlossaryTranslation.id
                == GlossaryTermVariant.glossary_translation_id,
            )
            .join(
                GlossaryTerm,
                GlossaryTerm.id == GlossaryTranslation.glossary_term_id,
            )
            .join(
                GlossaryProfile,
                GlossaryProfile.id == GlossaryTerm.glossary_profile_id,
            )
            .options(
                joinedload(GlossaryTermVariant.translation)
                .joinedload(GlossaryTranslation.term)
                .joinedload(GlossaryTerm.profile)
            )
            .where(GlossaryTermVariant.id == variant_id)
        )
        statement = self._profile_scope(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryTermVariant
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        profile_id: UUID | None = None,
        term_type: GlossaryTermType | None = None,
        language_code: GlossaryLanguageCode | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "termCode",
        sort_order: str = "asc",
    ) -> tuple[list[GlossaryTerm], int]:
        statement = self.base_statement()
        statement = self._scope_to_departments(statement, department_ids)
        if search:
            pattern = f"%{search.strip()}%"
            translation_exists = (
                select(GlossaryTranslation.id)
                .where(
                    GlossaryTranslation.glossary_term_id == GlossaryTerm.id,
                    or_(
                        GlossaryTranslation.term_text.ilike(pattern),
                        GlossaryTranslation.normalised_term.ilike(pattern),
                    ),
                )
                .exists()
            )
            statement = statement.where(
                or_(
                    GlossaryTerm.term_code.ilike(pattern),
                    GlossaryTerm.concept_name.ilike(pattern),
                    GlossaryTerm.description.ilike(pattern),
                    translation_exists,
                )
            )
        if profile_id is not None:
            statement = statement.where(
                GlossaryTerm.glossary_profile_id == profile_id
            )
        if term_type is not None:
            statement = statement.where(GlossaryTerm.term_type == term_type)
        if language_code is not None:
            statement = statement.where(
                select(GlossaryTranslation.id)
                .where(
                    GlossaryTranslation.glossary_term_id == GlossaryTerm.id,
                    GlossaryTranslation.language_code == language_code,
                )
                .exists()
            )
        if is_active is not None:
            statement = statement.where(GlossaryTerm.is_active.is_(is_active))
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
            "termCode": GlossaryTerm.term_code,
            "conceptName": GlossaryTerm.concept_name,
            "termType": GlossaryTerm.term_type,
            "updatedAt": GlossaryTerm.updated_at,
        }
        column = sort_columns.get(sort_by, GlossaryTerm.term_code)
        order = asc(column) if sort_order == "asc" else desc(column)
        result = await self.session.scalars(
            statement.order_by(order, GlossaryTerm.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def list_for_profiles(
        self,
        profile_ids: Sequence[UUID],
        *,
        active_only: bool = True,
    ) -> list[GlossaryTerm]:
        if not profile_ids:
            return []
        statement = self.base_statement().where(
            GlossaryTerm.glossary_profile_id.in_(list(profile_ids))
        )
        if active_only:
            statement = statement.where(GlossaryTerm.is_active.is_(True))
        result = await self.session.scalars(
            statement.order_by(
                GlossaryTerm.glossary_profile_id,
                GlossaryTerm.term_code,
            )
        )
        profile_priority = {
            profile_id: index
            for index, profile_id in enumerate(profile_ids)
        }
        return sorted(
            result.unique().all(),
            key=lambda item: (
                profile_priority.get(
                    item.glossary_profile_id,
                    len(profile_priority),
                ),
                item.term_code,
            ),
        )

    async def find_translation_conflict(
        self,
        *,
        term_id: UUID,
        language_code: GlossaryLanguageCode,
        normalised_term: str,
        exclude_id: UUID | None = None,
    ) -> GlossaryTranslation | None:
        statement = select(GlossaryTranslation).where(
            GlossaryTranslation.glossary_term_id == term_id,
            GlossaryTranslation.language_code == language_code,
            GlossaryTranslation.normalised_term == normalised_term,
        )
        if exclude_id is not None:
            statement = statement.where(
                GlossaryTranslation.id != exclude_id
            )
        return (
            await self.session.execute(statement.limit(1))
        ).scalar_one_or_none()

    async def find_variant_conflict(
        self,
        *,
        translation_id: UUID,
        normalised_variant: str,
        exclude_id: UUID | None = None,
    ) -> GlossaryTermVariant | None:
        statement = select(GlossaryTermVariant).where(
            GlossaryTermVariant.glossary_translation_id == translation_id,
            GlossaryTermVariant.normalised_variant == normalised_variant,
        )
        if exclude_id is not None:
            statement = statement.where(GlossaryTermVariant.id != exclude_id)
        return (
            await self.session.execute(statement.limit(1))
        ).scalar_one_or_none()

    @staticmethod
    def _scope_to_departments(statement, department_ids):
        if department_ids is None:
            return statement
        return statement.join(
            GlossaryProfile,
            GlossaryProfile.id == GlossaryTerm.glossary_profile_id,
        ).where(
            or_(
                GlossaryProfile.department_id.is_(None),
                GlossaryProfile.department_id.in_(list(department_ids)),
            )
        )

    @staticmethod
    def _profile_scope(statement, department_ids):
        if department_ids is None:
            return statement
        return statement.where(
            or_(
                GlossaryProfile.department_id.is_(None),
                GlossaryProfile.department_id.in_(list(department_ids)),
            )
        )
