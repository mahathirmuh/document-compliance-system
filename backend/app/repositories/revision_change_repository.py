"""Database-only operations for bounded revision changes."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revision_change import (
    RevisionChange,
    RevisionChangeType,
    RevisionEntityType,
)


class RevisionChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_add(
        self, changes: Sequence[RevisionChange]
    ) -> list[RevisionChange]:
        if not changes:
            return []
        self.session.add_all(changes)
        await self.session.flush()
        return list(changes)

    async def list_page(
        self,
        comparison_id: UUID,
        *,
        change_types: Sequence[RevisionChangeType] | None,
        entity_types: Sequence[RevisionEntityType] | None,
        language_code: str | None,
        section_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[RevisionChange], int]:
        predicates: list[object] = [
            RevisionChange.revision_comparison_id == comparison_id
        ]
        if change_types:
            predicates.append(RevisionChange.change_type.in_(change_types))
        if entity_types:
            predicates.append(RevisionChange.entity_type.in_(entity_types))
        if language_code:
            predicates.append(
                RevisionChange.language_code == language_code.lower()
            )
        if section_id:
            predicates.append(
                (RevisionChange.base_section_id == section_id)
                | (RevisionChange.target_section_id == section_id)
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                RevisionChange.base_text_snapshot.ilike(pattern)
                | RevisionChange.target_text_snapshot.ilike(pattern)
                | RevisionChange.source_reference_base.ilike(pattern)
                | RevisionChange.source_reference_target.ilike(pattern)
            )
        base = select(RevisionChange).where(*predicates)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                RevisionChange.created_at.asc(),
                RevisionChange.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def list_all(
        self,
        comparison_id: UUID,
        *,
        maximum: int,
    ) -> list[RevisionChange]:
        return list(
            await self.session.scalars(
                select(RevisionChange)
                .where(
                    RevisionChange.revision_comparison_id == comparison_id
                )
                .order_by(
                    RevisionChange.created_at.asc(),
                    RevisionChange.id.asc(),
                )
                .limit(maximum)
            )
        )
