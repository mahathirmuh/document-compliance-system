"""Persistence operations for structured extracted tables and cells."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.extracted_container import ExtractedContainer
from app.models.extracted_table import ExtractedTable
from app.models.extracted_table_cell import ExtractedTableCell


class ExtractedTableRepository:
    """Database-only table and table-cell operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(
        self,
        tables: Sequence[ExtractedTable],
    ) -> list[ExtractedTable]:
        if not tables:
            return []
        self.session.add_all(tables)
        await self.session.flush()
        return list(tables)

    async def bulk_create_cells(
        self,
        cells: Sequence[ExtractedTableCell],
    ) -> list[ExtractedTableCell]:
        if not cells:
            return []
        self.session.add_all(cells)
        await self.session.flush()
        return list(cells)

    async def list(
        self,
        extraction_run_id: UUID,
        *,
        container_id: UUID | None = None,
        search: str | None = None,
        include_cells: bool = False,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[ExtractedTable], int]:
        predicates: list[object] = [
            ExtractedTable.extraction_run_id == extraction_run_id
        ]
        if container_id is not None:
            predicates.append(ExtractedTable.container_id == container_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    ExtractedTable.raw_text.ilike(pattern),
                    ExtractedTable.source_reference.ilike(pattern),
                )
            )
        base = (
            select(ExtractedTable)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedTable.container_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = base.options(
            joinedload(ExtractedTable.container)
        ).order_by(
            ExtractedContainer.container_index.asc(),
            ExtractedTable.table_index.asc(),
            ExtractedTable.id.asc(),
        )
        if include_cells:
            statement = statement.options(
                selectinload(ExtractedTable.cells)
            )
        statement = statement.offset((page - 1) * page_size).limit(
            page_size
        )
        return (
            list((await self.session.scalars(statement)).unique().all()),
            total,
        )

    async def list_cells(
        self,
        extracted_table_id: UUID,
        *,
        page: int = 1,
        page_size: int = 200,
    ) -> tuple[list[ExtractedTableCell], int]:
        base = select(ExtractedTableCell).where(
            ExtractedTableCell.extracted_table_id == extracted_table_id
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                ExtractedTableCell.row_index,
                ExtractedTableCell.column_index,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def count(self, extraction_run_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(ExtractedTable.id)).where(
                    ExtractedTable.extraction_run_id == extraction_run_id
                )
            )
            or 0
        )

    async def search(
        self,
        extraction_run_id: UUID,
        query: str,
        *,
        limit: int = 100,
    ) -> tuple[list[ExtractedTable], int]:
        pattern = f"%{query.strip()}%"
        base = (
            select(ExtractedTable)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedTable.container_id,
            )
            .where(
                ExtractedTable.extraction_run_id == extraction_run_id,
                or_(
                    ExtractedTable.raw_text.ilike(pattern),
                    ExtractedTable.source_reference.ilike(pattern),
                    ExtractedTable.cells.any(
                        ExtractedTableCell.normalised_text.ilike(pattern)
                    ),
                ),
            )
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base
            .options(joinedload(ExtractedTable.container))
            .order_by(
                ExtractedContainer.container_index.asc(),
                ExtractedTable.table_index.asc(),
                ExtractedTable.id.asc(),
            )
            .limit(limit)
        )
        return (
            list(
                (await self.session.scalars(statement)).unique().all()
            ),
            total,
        )

    async def delete_by_run(self, extraction_run_id: UUID) -> int:
        result = await self.session.execute(
            delete(ExtractedTable).where(
                ExtractedTable.extraction_run_id == extraction_run_id
            )
        )
        await self.session.flush()
        return int(result.rowcount or 0)
