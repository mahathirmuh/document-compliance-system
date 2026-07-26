"""Batch persistence and paginated reads for OCR text blocks."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_block import OCRBlock
from app.models.ocr_page_result import OCRPageResult


class OCRBlockRepository:
    """Store large block sets in bounded batches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def batch_insert(
        self,
        rows: Iterable[dict[str, object]],
        *,
        batch_size: int = 1000,
    ) -> int:
        if batch_size < 1:
            raise ValueError("OCR batch size must be positive.")
        batch: list[dict[str, object]] = []
        inserted = 0
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                await self.session.execute(insert(OCRBlock), batch)
                inserted += len(batch)
                batch.clear()
        if batch:
            await self.session.execute(insert(OCRBlock), batch)
            inserted += len(batch)
        await self.session.flush()
        return inserted

    async def list_by_run(
        self,
        ocr_run_id: UUID,
        *,
        page_number: int | None = None,
        page_numbers: Sequence[int] | None = None,
        minimum_confidence: float | None = None,
        maximum_confidence: float | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[tuple[OCRBlock, int]], int]:
        if page_number is not None and page_numbers is not None:
            raise ValueError("Use either page_number or page_numbers, not both.")
        statement = (
            select(OCRBlock, OCRPageResult.page_number)
            .join(
                OCRPageResult,
                OCRPageResult.id == OCRBlock.ocr_page_result_id,
            )
            .where(OCRBlock.ocr_run_id == ocr_run_id)
        )
        if page_number is not None:
            statement = statement.where(OCRPageResult.page_number == page_number)
        if page_numbers is not None:
            if not page_numbers:
                return [], 0
            statement = statement.where(
                OCRPageResult.page_number.in_(tuple(page_numbers))
            )
        if minimum_confidence is not None:
            statement = statement.where(OCRBlock.confidence >= minimum_confidence)
        if maximum_confidence is not None:
            statement = statement.where(OCRBlock.confidence <= maximum_confidence)
        if search:
            statement = statement.where(
                OCRBlock.normalised_text.ilike(f"%{search.strip()}%")
            )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            or 0
        )
        rows = await self.session.execute(
            statement.order_by(
                OCRPageResult.page_number,
                OCRBlock.block_order,
                OCRBlock.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return [(row[0], int(row[1])) for row in rows.all()], total

    async def list_for_page(
        self,
        page_result_id: UUID,
    ) -> list[OCRBlock]:
        rows = await self.session.scalars(
            select(OCRBlock)
            .where(OCRBlock.ocr_page_result_id == page_result_id)
            .order_by(OCRBlock.block_order, OCRBlock.id)
        )
        return list(rows.all())

    async def count_below_confidence_by_run(
        self,
        ocr_run_ids: Iterable[UUID],
        *,
        threshold: float,
    ) -> dict[UUID, int]:
        run_ids = tuple(dict.fromkeys(ocr_run_ids))
        if not run_ids:
            return {}
        rows = await self.session.execute(
            select(
                OCRBlock.ocr_run_id,
                func.count(OCRBlock.id),
            )
            .where(
                OCRBlock.ocr_run_id.in_(run_ids),
                OCRBlock.confidence < threshold,
            )
            .group_by(OCRBlock.ocr_run_id)
        )
        return {run_id: int(count) for run_id, count in rows.all()}
