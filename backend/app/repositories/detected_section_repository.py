"""Persistence operations for detected canonical sections."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.detected_section import DetectedSection
from app.models.section_language_result import SectionLanguageResult


class DetectedSectionRepository:
    """Batch persistence and run-scoped reads for detected sections."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        section_id: UUID,
    ) -> DetectedSection | None:
        statement = (
            select(DetectedSection)
            .options(selectinload(DetectedSection.language_results))
            .where(DetectedSection.id == section_id)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add_many(
        self,
        sections: Sequence[DetectedSection],
        *,
        batch_size: int = 1000,
    ) -> list[DetectedSection]:
        items = list(sections)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_for_run(
        self,
        compliance_run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> list[DetectedSection]:
        result = await self.session.scalars(
            select(DetectedSection)
            .options(selectinload(DetectedSection.language_results))
            .where(DetectedSection.compliance_run_id == compliance_run_id)
            .order_by(DetectedSection.section_order, DetectedSection.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all())

    async def count_for_run(self, compliance_run_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(DetectedSection.id)).where(
                        DetectedSection.compliance_run_id
                        == compliance_run_id
                    )
                )
            )
            or 0
        )

    async def count_language_results_for_run(
        self,
        compliance_run_id: UUID,
    ) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(SectionLanguageResult.id))
                    .join(
                        DetectedSection,
                        DetectedSection.id
                        == SectionLanguageResult.detected_section_id,
                    )
                    .where(
                        DetectedSection.compliance_run_id
                        == compliance_run_id
                    )
                )
            )
            or 0
        )

    async def count_language_results_for_run_page(
        self,
        compliance_run_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> int:
        section_ids = (
            select(DetectedSection.id)
            .where(
                DetectedSection.compliance_run_id == compliance_run_id
            )
            .order_by(
                DetectedSection.section_order,
                DetectedSection.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return int(
            (
                await self.session.scalar(
                    select(func.count(SectionLanguageResult.id)).where(
                        SectionLanguageResult.detected_section_id.in_(
                            section_ids
                        )
                    )
                )
            )
            or 0
        )
