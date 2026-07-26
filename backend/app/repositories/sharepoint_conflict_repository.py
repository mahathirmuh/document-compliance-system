"""SharePoint conflict persistence with department-scoped listing."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_enums import SyncConflictStatus
from app.models.sharepoint_sync_conflict import SharePointSyncConflict
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.models.sharepoint_sync_profile import SharePointSyncProfile


class SharePointConflictRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        conflict: SharePointSyncConflict,
    ) -> SharePointSyncConflict:
        self.session.add(conflict)
        await self.session.flush()
        return conflict

    async def get_by_id(
        self,
        conflict_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> SharePointSyncConflict | None:
        statement = select(SharePointSyncConflict).where(
            SharePointSyncConflict.id == conflict_id
        )
        if department_ids is not None:
            statement = (
                statement.join(
                    SharePointSyncJob,
                    SharePointSyncJob.id
                    == SharePointSyncConflict.sync_job_id,
                )
                .join(
                    SharePointSyncProfile,
                    SharePointSyncProfile.id
                    == SharePointSyncJob.sync_profile_id,
                )
                .where(
                    SharePointSyncProfile.department_id.in_(
                        list(department_ids)
                    )
                )
            )
        if for_update:
            statement = statement.with_for_update(
                of=SharePointSyncConflict
            )
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        statuses: Sequence[SyncConflictStatus] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointSyncConflict], int]:
        base = select(SharePointSyncConflict)
        if department_ids is not None:
            base = (
                base.join(
                    SharePointSyncJob,
                    SharePointSyncJob.id
                    == SharePointSyncConflict.sync_job_id,
                )
                .join(
                    SharePointSyncProfile,
                    SharePointSyncProfile.id
                    == SharePointSyncJob.sync_profile_id,
                )
                .where(
                    SharePointSyncProfile.department_id.in_(
                        list(department_ids)
                    )
                )
            )
        if statuses:
            base = base.where(
                SharePointSyncConflict.status.in_(list(statuses))
            )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(SharePointSyncConflict.detected_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total
