"""Persistence and ordered reads for language container summaries."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.language_container_summary import LanguageContainerSummary


class LanguageContainerSummaryRepository:
    """Database-only container-summary operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(
        self,
        summaries: Sequence[LanguageContainerSummary],
    ) -> list[LanguageContainerSummary]:
        if not summaries:
            return []
        self.session.add_all(summaries)
        await self.session.flush()
        return list(summaries)

    async def list(
        self,
        language_detection_run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[LanguageContainerSummary], int]:
        predicate = (
            LanguageContainerSummary.language_detection_run_id
            == language_detection_run_id
        )
        total = int(
            await self.session.scalar(
                select(func.count(LanguageContainerSummary.id)).where(
                    predicate
                )
            )
            or 0
        )
        statement = (
            select(LanguageContainerSummary)
            .where(predicate)
            .order_by(
                LanguageContainerSummary.container_index,
                LanguageContainerSummary.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total
