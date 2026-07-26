"""Persistence and paginated search for extracted content blocks."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import String, delete, func, literal_column, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.elements import ColumnElement

from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import ExtractedContainer


def _block_text_search_predicate(
    query: str,
    *,
    dialect_name: str,
) -> ColumnElement[bool]:
    """Build an indexed PostgreSQL predicate with a SQLite-safe fallback."""
    if dialect_name == "postgresql":
        simple_config: ColumnElement[str] = literal_column(
            "'simple'",
            type_=String(),
        )
        indexed_content = (
            ExtractedBlock.normalised_text
            + literal_column("' '")
            + ExtractedBlock.source_reference
        )
        document_vector = func.to_tsvector(
            simple_config,
            indexed_content,
        )
        search_query = func.plainto_tsquery(simple_config, query)
        return document_vector.bool_op("@@")(search_query)
    return ExtractedBlock.normalised_text.ilike(f"%{query}%")


def _container_name_search_predicate(query: str) -> ColumnElement[bool]:
    """Build the predicate matching the PostgreSQL container-name GIN index."""
    simple_config: ColumnElement[str] = literal_column(
        "'simple'",
        type_=String(),
    )
    document_vector = func.to_tsvector(
        simple_config,
        ExtractedContainer.name,
    )
    search_query = func.plainto_tsquery(simple_config, query)
    return document_vector.bool_op("@@")(search_query)


def _block_search_predicate(
    query: str,
    *,
    extraction_run_id: UUID,
    dialect_name: str,
    include_container_name: bool,
) -> ColumnElement[bool]:
    """Search content through GIN on PostgreSQL and ILIKE on SQLite."""
    text_predicate = _block_text_search_predicate(
        query,
        dialect_name=dialect_name,
    )
    if dialect_name == "postgresql":
        if not include_container_name:
            return text_predicate
        matching_containers = select(ExtractedContainer.id).where(
            ExtractedContainer.extraction_run_id == extraction_run_id,
            _container_name_search_predicate(query),
        )
        return or_(
            text_predicate,
            ExtractedBlock.container_id.in_(matching_containers),
        )

    pattern = f"%{query}%"
    predicates = [
        text_predicate,
        ExtractedBlock.source_reference.ilike(pattern),
    ]
    if include_container_name:
        predicates.append(ExtractedContainer.name.ilike(pattern))
    return or_(*predicates)


class ExtractedBlockRepository:
    """Database-only block operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(
        self,
        blocks: Sequence[ExtractedBlock],
    ) -> list[ExtractedBlock]:
        if not blocks:
            return []
        self.session.add_all(blocks)
        await self.session.flush()
        return list(blocks)

    async def list(
        self,
        extraction_run_id: UUID,
        *,
        container_id: UUID | None = None,
        block_type: ExtractedBlockType | None = None,
        block_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 100,
        sort_order: str = "asc",
    ) -> tuple[builtins.list[ExtractedBlock], int]:
        predicates: list[ColumnElement[bool]] = [
            ExtractedBlock.extraction_run_id == extraction_run_id
        ]
        if container_id is not None:
            predicates.append(ExtractedBlock.container_id == container_id)
        if block_type is not None:
            predicates.append(ExtractedBlock.block_type == block_type)
        if block_ids is not None:
            if not block_ids:
                return [], 0
            predicates.append(ExtractedBlock.id.in_(block_ids))
        if search and search.strip():
            normalized_query = search.strip()
            dialect_name = self.session.get_bind().dialect.name
            predicates.append(
                _block_search_predicate(
                    normalized_query,
                    extraction_run_id=extraction_run_id,
                    dialect_name=dialect_name,
                    include_container_name=False,
                )
            )
        base = (
            select(ExtractedBlock)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedBlock.container_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        descending = sort_order.lower() == "desc"
        order_columns = (
            ExtractedContainer.container_index,
            ExtractedBlock.block_order,
            ExtractedBlock.id,
        )
        ordering = tuple(
            column.desc() if descending else column.asc()
            for column in order_columns
        )
        statement = (
            base.options(joinedload(ExtractedBlock.container))
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return (
            list((await self.session.scalars(statement)).unique().all()),
            total,
        )

    async def count(
        self,
        extraction_run_id: UUID,
        *,
        container_id: UUID | None = None,
    ) -> int:
        statement = select(func.count(ExtractedBlock.id)).where(
            ExtractedBlock.extraction_run_id == extraction_run_id
        )
        if container_id is not None:
            statement = statement.where(
                ExtractedBlock.container_id == container_id
            )
        return int(await self.session.scalar(statement) or 0)

    async def search(
        self,
        extraction_run_id: UUID,
        query: str,
        *,
        limit: int = 500,
    ) -> tuple[builtins.list[ExtractedBlock], int]:
        normalized_query = query.strip()
        dialect_name = self.session.get_bind().dialect.name
        predicate = _block_search_predicate(
            normalized_query,
            extraction_run_id=extraction_run_id,
            dialect_name=dialect_name,
            include_container_name=True,
        )
        base = (
            select(ExtractedBlock)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedBlock.container_id,
            )
            .where(
                ExtractedBlock.extraction_run_id == extraction_run_id,
                predicate,
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
            .options(joinedload(ExtractedBlock.container))
            .order_by(
                ExtractedContainer.container_index.asc(),
                ExtractedBlock.block_order.asc(),
                ExtractedBlock.id.asc(),
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
            delete(ExtractedBlock).where(
                ExtractedBlock.extraction_run_id == extraction_run_id
            )
        )
        await self.session.flush()
        return int(cast(CursorResult[Any], result).rowcount or 0)
