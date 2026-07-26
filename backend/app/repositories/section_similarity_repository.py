"""Persistence and bounded queries for section similarity aggregates."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.similarity_section_summary import SectionSimilaritySummary


class SectionSimilarityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        summaries: Sequence[SectionSimilaritySummary],
        *,
        batch_size: int = 500,
    ) -> list[SectionSimilaritySummary]:
        items = list(summaries)
        for offset in range(0, len(items), max(1, batch_size)):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_for_run(
        self,
        run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[SectionSimilaritySummary], int]:
        statement = select(SectionSimilaritySummary).where(
            SectionSimilaritySummary.similarity_run_id == run_id
        )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(statement.subquery())
                )
            )
            or 0
        )
        rows = await self.session.scalars(
            statement.order_by(
                SectionSimilaritySummary.canonical_section_code,
                SectionSimilaritySummary.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.all()), total

    async def count_for_run(self, run_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(SectionSimilaritySummary.id)).where(
                        SectionSimilaritySummary.similarity_run_id == run_id
                    )
                )
            )
            or 0
        )
