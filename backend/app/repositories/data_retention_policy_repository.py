"""Persistence queries for approved data-retention policies."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_retention_policy import (
    DataRetentionPolicy,
    RetentionEntityType,
)


class DataRetentionPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, policy: DataRetentionPolicy) -> DataRetentionPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_by_id(
        self,
        policy_id: UUID,
        *,
        for_update: bool = False,
    ) -> DataRetentionPolicy | None:
        statement = select(DataRetentionPolicy).where(
            DataRetentionPolicy.id == policy_id
        )
        if for_update:
            statement = statement.with_for_update(of=DataRetentionPolicy)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        entity_type: RetentionEntityType | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[DataRetentionPolicy], int]:
        predicates = []
        if entity_type is not None:
            predicates.append(DataRetentionPolicy.entity_type == entity_type)
        if not include_inactive:
            predicates.append(DataRetentionPolicy.is_active.is_(True))
        base = select(DataRetentionPolicy).where(*predicates)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            base.order_by(DataRetentionPolicy.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total

    async def active_for_entity(
        self,
        entity_type: RetentionEntityType,
    ) -> list[DataRetentionPolicy]:
        statement = (
            select(DataRetentionPolicy)
            .where(
                DataRetentionPolicy.entity_type == entity_type,
                DataRetentionPolicy.is_active.is_(True),
            )
            .order_by(DataRetentionPolicy.created_at.asc())
        )
        return list(await self.session.scalars(statement))
