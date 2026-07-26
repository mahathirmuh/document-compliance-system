"""Database-only advanced report snapshot operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)


class ReportSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, snapshot: ReportSnapshot) -> ReportSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    @staticmethod
    def _scope_predicate(
        department_ids: Sequence[UUID] | None,
    ) -> object | None:
        if department_ids is None:
            return None
        if not department_ids:
            return ReportSnapshot.id.is_(None)
        return ReportSnapshot.scope_department_id.in_(department_ids)

    async def get_by_id(
        self,
        snapshot_id: UUID,
        *,
        department_ids: Sequence[UUID] | None,
        for_update: bool = False,
    ) -> ReportSnapshot | None:
        predicates: list[object] = [ReportSnapshot.id == snapshot_id]
        scope = self._scope_predicate(department_ids)
        if scope is not None:
            predicates.append(scope)
        statement = select(ReportSnapshot).where(*predicates)
        if for_update:
            statement = statement.with_for_update(of=ReportSnapshot)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        report_types: Sequence[AdvancedReportType] | None,
        statuses: Sequence[ReportSnapshotStatus] | None,
        job_statuses: Sequence[ReportJobStatus] | None,
        page: int,
        page_size: int,
        file_formats: Sequence[ReportFileFormat] | None = None,
        generated_from: datetime | None = None,
        generated_to: datetime | None = None,
    ) -> tuple[list[ReportSnapshot], int]:
        predicates: list[object] = []
        scope = self._scope_predicate(department_ids)
        if scope is not None:
            predicates.append(scope)
        if report_types:
            predicates.append(ReportSnapshot.report_type.in_(report_types))
        if statuses:
            predicates.append(ReportSnapshot.status.in_(statuses))
        if job_statuses:
            predicates.append(ReportSnapshot.job_status.in_(job_statuses))
        if file_formats:
            predicates.append(
                ReportSnapshot.file_format.in_(file_formats)
            )
        if generated_from is not None:
            predicates.append(
                ReportSnapshot.generated_at >= generated_from
            )
        if generated_to is not None:
            predicates.append(ReportSnapshot.generated_at < generated_to)
        base = select(ReportSnapshot).where(*predicates)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.order_by(
                ReportSnapshot.created_at.desc(),
                ReportSnapshot.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await self.session.scalars(statement)), total
