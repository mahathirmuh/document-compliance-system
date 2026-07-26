"""Persistence queries for retained glossary matches."""

from collections import Counter
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryMatchType,
)
from app.models.glossary_match import GlossaryMatch
from app.models.glossary_term import GlossaryTerm


class GlossaryMatchRepository:
    """Batch persistence and bounded match retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        items: Sequence[GlossaryMatch],
        *,
        batch_size: int = 1000,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive.")
        for offset in range(0, len(items), batch_size):
            self.session.add_all(list(items[offset : offset + batch_size]))
            await self.session.flush()

    async def list_page(
        self,
        run_id: UUID,
        *,
        language_code: GlossaryLanguageCode | None = None,
        term_id: UUID | None = None,
        match_type: GlossaryMatchType | None = None,
        is_preferred: bool | None = None,
        is_forbidden: bool | None = None,
        has_exception: bool | None = None,
        page: int = 1,
        page_size: int = 100,
        sort_order: str = "asc",
    ) -> tuple[list[GlossaryMatch], int]:
        statement = (
            select(GlossaryMatch)
            .options(
                joinedload(GlossaryMatch.validation_run),
                joinedload(GlossaryMatch.term),
            )
            .where(GlossaryMatch.glossary_validation_run_id == run_id)
        )
        if language_code is not None:
            statement = statement.where(
                GlossaryMatch.language_code == language_code
            )
        if term_id is not None:
            statement = statement.where(
                GlossaryMatch.glossary_term_id == term_id
            )
        if match_type is not None:
            statement = statement.where(
                GlossaryMatch.match_type == match_type
            )
        if is_preferred is not None:
            statement = statement.where(
                GlossaryMatch.is_preferred.is_(is_preferred)
            )
        if is_forbidden is not None:
            statement = statement.where(
                GlossaryMatch.is_forbidden.is_(is_forbidden)
            )
        if has_exception is not None:
            statement = statement.where(
                GlossaryMatch.exception_id.is_not(None)
                if has_exception
                else GlossaryMatch.exception_id.is_(None)
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
        order = (
            asc(GlossaryMatch.created_at)
            if sort_order == "asc"
            else desc(GlossaryMatch.created_at)
        )
        result = await self.session.scalars(
            statement.order_by(order, GlossaryMatch.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def counts_for_run(self, run_id: UUID) -> dict[str, object]:
        rows = (
            await self.session.execute(
                select(
                    GlossaryMatch.language_code,
                    GlossaryMatch.is_preferred,
                    GlossaryMatch.is_forbidden,
                    GlossaryMatch.exception_id,
                    func.count(GlossaryMatch.id),
                )
                .where(GlossaryMatch.glossary_validation_run_id == run_id)
                .group_by(
                    GlossaryMatch.language_code,
                    GlossaryMatch.is_preferred,
                    GlossaryMatch.is_forbidden,
                    GlossaryMatch.exception_id,
                )
            )
        ).all()
        languages: Counter[str] = Counter()
        total = 0
        preferred = 0
        forbidden = 0
        exceptions = 0
        for language, is_preferred, is_forbidden, exception_id, count in rows:
            amount = int(count)
            total += amount
            languages[language.value] += amount
            preferred += amount if is_preferred else 0
            forbidden += amount if is_forbidden else 0
            exceptions += amount if exception_id is not None else 0
        return {
            "matchCount": total,
            "preferredMatches": preferred,
            "forbiddenMatches": forbidden,
            "exceptionMatches": exceptions,
            "languageCounts": dict(languages),
        }

    async def historical_term_ids(self, term_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(GlossaryMatch.id)
                .where(GlossaryMatch.glossary_term_id == term_id)
                .limit(1)
            )
        )

    async def term_references(
        self,
        run_id: UUID,
    ) -> dict[UUID, GlossaryTerm]:
        del run_id
        return {}
