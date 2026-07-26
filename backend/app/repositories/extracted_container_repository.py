"""Persistence operations for extracted logical containers."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)


class ExtractedContainerRepository:
    """Database-only container operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(
        self,
        containers: Sequence[ExtractedContainer],
    ) -> builtins.list[ExtractedContainer]:
        if not containers:
            return []
        self.session.add_all(containers)
        await self.session.flush()
        return list(containers)

    async def list(
        self,
        extraction_run_id: UUID,
        *,
        container_type: ExtractedContainerType | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[ExtractedContainer], int]:
        predicates: list[ColumnElement[bool]] = [
            ExtractedContainer.extraction_run_id == extraction_run_id
        ]
        if container_type is not None:
            predicates.append(
                ExtractedContainer.container_type == container_type
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    ExtractedContainer.name.ilike(pattern),
                    ExtractedContainer.title.ilike(pattern),
                    ExtractedContainer.normalised_text.ilike(pattern),
                )
            )
        base = select(ExtractedContainer).where(*predicates)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                ExtractedContainer.container_index,
                ExtractedContainer.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def count(self, extraction_run_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(ExtractedContainer.id)).where(
                    ExtractedContainer.extraction_run_id
                    == extraction_run_id
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
    ) -> builtins.list[ExtractedContainer]:
        pattern = f"%{query.strip()}%"
        statement = (
            select(ExtractedContainer)
            .where(
                ExtractedContainer.extraction_run_id
                == extraction_run_id,
                or_(
                    ExtractedContainer.name.ilike(pattern),
                    ExtractedContainer.title.ilike(pattern),
                    ExtractedContainer.normalised_text.ilike(pattern),
                ),
            )
            .order_by(ExtractedContainer.container_index)
            .limit(limit)
        )
        return list(await self.session.scalars(statement))

    async def delete_by_run(self, extraction_run_id: UUID) -> int:
        result = await self.session.execute(
            delete(ExtractedContainer).where(
                ExtractedContainer.extraction_run_id == extraction_run_id
            )
        )
        await self.session.flush()
        return int(cast(CursorResult[Any], result).rowcount or 0)
