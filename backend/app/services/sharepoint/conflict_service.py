"""Scoped SharePoint conflict assignment and explicit resolution workflow."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.sharepoint_enums import (
    SyncConflictResolution,
    SyncConflictStatus,
    SyncItemOperation,
    SyncItemStatus,
)
from app.models.sharepoint_sync_conflict import SharePointSyncConflict
from app.models.user import User
from app.repositories.sharepoint_conflict_repository import (
    SharePointConflictRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_sync import (
    SharePointConflictListResponse,
    SharePointConflictResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)
from app.utils.datetime import utc_now

_RESOLUTION_OPERATIONS = {
    SyncConflictResolution.KEEP_LOCAL: SyncItemOperation.UPDATE_REMOTE,
    SyncConflictResolution.KEEP_REMOTE: SyncItemOperation.UPDATE_LOCAL,
    SyncConflictResolution.KEEP_BOTH: SyncItemOperation.CREATE_REMOTE,
    SyncConflictResolution.MERGE_METADATA: (
        SyncItemOperation.UPDATE_REMOTE_METADATA
    ),
    SyncConflictResolution.IGNORE_REMOTE_CHANGE: SyncItemOperation.SKIP,
    SyncConflictResolution.IGNORE_LOCAL_CHANGE: SyncItemOperation.SKIP,
}


class SharePointConflictService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.conflicts = SharePointConflictRepository(session)
        self.sync = SharePointSyncRepository(session)

    async def list(
        self,
        *,
        statuses: list[SyncConflictStatus] | None,
        page: int,
        page_size: int,
    ) -> SharePointConflictListResponse:
        items, total = await self.conflicts.list_page(
            department_ids=self.policy.department_ids(),
            statuses=statuses,
            page=page,
            page_size=page_size,
        )
        return SharePointConflictListResponse(
            items=[
                SharePointConflictResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def get(
        self,
        conflict_id: UUID,
    ) -> SharePointConflictResponse:
        conflict = await self._get(conflict_id)
        return SharePointConflictResponse.model_validate(conflict)

    async def assign(
        self,
        conflict_id: UUID,
        *,
        assigned_to: UUID,
    ) -> SharePointConflictResponse:
        conflict = await self._get(conflict_id, for_update=True)
        if conflict.status not in {
            SyncConflictStatus.OPEN,
            SyncConflictStatus.IN_REVIEW,
        }:
            raise sharepoint_error(
                "Only an open conflict can be assigned.",
                code="SHAREPOINT_CONFLICT",
                status_code=HTTPStatus.CONFLICT,
            )
        conflict.assigned_to = assigned_to
        conflict.status = SyncConflictStatus.IN_REVIEW
        await self.audit_if_registered(
            "ASSIGN_SHAREPOINT_CONFLICT",
            entity_type="SharePointSyncConflict",
            entity_id=conflict.id,
            description="SharePoint conflict assigned.",
            values={"assignedTo": str(assigned_to)},
        )
        await self.session.commit()
        return SharePointConflictResponse.model_validate(conflict)

    async def resolve(
        self,
        conflict_id: UUID,
        *,
        resolution: SyncConflictResolution,
        comment: str,
    ) -> SharePointConflictResponse:
        conflict = await self._get(conflict_id, for_update=True)
        if conflict.status not in {
            SyncConflictStatus.OPEN,
            SyncConflictStatus.IN_REVIEW,
        }:
            raise sharepoint_error(
                "This SharePoint conflict is already closed.",
                code="SHAREPOINT_CONFLICT",
                status_code=HTTPStatus.CONFLICT,
            )
        if not comment.strip():
            raise sharepoint_error(
                "A conflict resolution comment is required.",
                code="SHAREPOINT_CONFLICT",
                field="comment",
            )
        item = (
            await self.sync.get_item(conflict.sync_item_id, for_update=True)
            if conflict.sync_item_id is not None
            else None
        )
        if item is not None:
            item.operation = _RESOLUTION_OPERATIONS[resolution]
            item.status = (
                SyncItemStatus.SKIPPED
                if item.operation is SyncItemOperation.SKIP
                else SyncItemStatus.QUEUED
            )
            metadata = dict(item.metadata_json or {})
            metadata["conflictResolution"] = resolution.value
            metadata["requiresUserApprovedExecution"] = True
            if resolution is SyncConflictResolution.KEEP_BOTH:
                metadata["safeCopySuffix"] = f"conflict-{str(conflict.id)[:8]}"
            item.metadata_json = metadata
        conflict.status = SyncConflictStatus.RESOLVED
        conflict.resolution = resolution
        conflict.resolved_by = self.user.id
        conflict.resolved_at = utc_now()
        conflict.resolution_comment = comment.strip()
        await self.audit_if_registered(
            "RESOLVE_SHAREPOINT_CONFLICT",
            entity_type="SharePointSyncConflict",
            entity_id=conflict.id,
            description="SharePoint conflict explicitly resolved.",
            values={
                "resolution": resolution.value,
                "syncItemQueued": item is not None
                and item.status is SyncItemStatus.QUEUED,
            },
        )
        await self.session.commit()
        if item is not None and item.status is SyncItemStatus.QUEUED:
            from app.workers.sharepoint_tasks import (
                process_sharepoint_sync_item,
            )

            process_sharepoint_sync_item.apply_async(
                args=[str(item.id)],
                queue=get_settings().sharepoint_queue_name,
                task_id=str(uuid4()),
            )
        return SharePointConflictResponse.model_validate(conflict)

    async def ignore(
        self,
        conflict_id: UUID,
        *,
        comment: str,
    ) -> SharePointConflictResponse:
        conflict = await self._get(conflict_id, for_update=True)
        if conflict.status not in {
            SyncConflictStatus.OPEN,
            SyncConflictStatus.IN_REVIEW,
        }:
            raise sharepoint_error(
                "This SharePoint conflict is already closed.",
                code="SHAREPOINT_CONFLICT",
                status_code=HTTPStatus.CONFLICT,
            )
        conflict.status = SyncConflictStatus.IGNORED
        conflict.resolved_by = self.user.id
        conflict.resolved_at = utc_now()
        conflict.resolution_comment = comment.strip()
        await self.audit_if_registered(
            "IGNORE_SHAREPOINT_CONFLICT",
            entity_type="SharePointSyncConflict",
            entity_id=conflict.id,
            description="SharePoint conflict ignored.",
        )
        await self.session.commit()
        return SharePointConflictResponse.model_validate(conflict)

    async def _get(
        self,
        conflict_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointSyncConflict:
        conflict = await self.conflicts.get_by_id(
            conflict_id,
            department_ids=self.policy.department_ids(),
            for_update=for_update,
        )
        if conflict is None:
            raise sharepoint_error(
                "SharePoint conflict was not found.",
                code="SHAREPOINT_CONFLICT",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return conflict
