"""Database access for per-page OCR results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.ocr_page_result import OCRPageResult, OCRPageStatus


class OCRPageResultRepository:
    """Persist and page OCR page results without business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, page: OCRPageResult) -> OCRPageResult:
        self.session.add(page)
        await self.session.flush()
        return page

    async def get_by_run_and_page(
        self,
        ocr_run_id: UUID,
        page_number: int,
        *,
        include_blocks: bool = False,
    ) -> OCRPageResult | None:
        statement = select(OCRPageResult).where(
            OCRPageResult.ocr_run_id == ocr_run_id,
            OCRPageResult.page_number == page_number,
        )
        if include_blocks:
            statement = statement.options(selectinload(OCRPageResult.blocks))
        return await self.session.scalar(statement)

    async def list_by_run(
        self,
        ocr_run_id: UUID,
        *,
        statuses: Sequence[OCRPageStatus] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[OCRPageResult], int]:
        predicates: list[ColumnElement[bool]] = [
            OCRPageResult.ocr_run_id == ocr_run_id
        ]
        if statuses:
            predicates.append(OCRPageResult.status.in_(statuses))
        total_value = await self.session.scalar(
            select(func.count(OCRPageResult.id)).where(*predicates)
        )
        total = int(total_value or 0)
        rows = await self.session.scalars(
            select(OCRPageResult)
            .where(*predicates)
            .order_by(OCRPageResult.page_number, OCRPageResult.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.all()), total
