"""Persistence operations for section-language evidence."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.section_language_result import SectionLanguageResult


class SectionLanguageResultRepository:
    """Batch persistence and section-scoped reads."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        results: Sequence[SectionLanguageResult],
        *,
        batch_size: int = 1000,
    ) -> list[SectionLanguageResult]:
        items = list(results)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_for_section(
        self,
        detected_section_id: UUID,
    ) -> list[SectionLanguageResult]:
        result = await self.session.scalars(
            select(SectionLanguageResult)
            .where(
                SectionLanguageResult.detected_section_id
                == detected_section_id
            )
            .order_by(SectionLanguageResult.language_code)
        )
        return list(result.all())
