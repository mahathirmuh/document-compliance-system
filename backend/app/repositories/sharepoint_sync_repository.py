"""Durable SharePoint sync profiles, jobs, items, and delta cursors."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.sharepoint_delta_state import SharePointDeltaState
from app.models.sharepoint_enums import (
    ACTIVE_SYNC_JOB_STATUSES,
    FolderMappingScope,
    SharePointSyncJobStatus,
    SyncDirection,
    SyncJobType,
)
from app.models.sharepoint_sync_item import SharePointSyncItem
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.models.sharepoint_sync_profile import SharePointSyncProfile


class SharePointSyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_profile(
        self,
        profile: SharePointSyncProfile,
    ) -> SharePointSyncProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile(
        self,
        profile_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointSyncProfile | None:
        statement = select(SharePointSyncProfile).where(
            SharePointSyncProfile.id == profile_id
        )
        if for_update:
            statement = statement.with_for_update(of=SharePointSyncProfile)
        return await self.session.scalar(statement)

    async def list_profiles(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointSyncProfile], int]:
        base = select(SharePointSyncProfile)
        if department_ids is not None:
            base = base.where(
                SharePointSyncProfile.department_id.in_(list(department_ids))
            )
        if not include_inactive:
            base = base.where(SharePointSyncProfile.is_active.is_(True))
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(SharePointSyncProfile.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def resolve_profile(
        self,
        *,
        department_id: UUID,
        section_id: UUID | None,
        document_type_id: UUID,
        required_direction: SyncDirection | None = None,
    ) -> SharePointSyncProfile | None:
        statement = select(SharePointSyncProfile).where(
            SharePointSyncProfile.is_active.is_(True)
        )
        if required_direction is not None:
            statement = statement.where(
                SharePointSyncProfile.direction.in_(
                    (
                        required_direction,
                        SyncDirection.BIDIRECTIONAL,
                    )
                )
            )
        profiles = list(await self.session.scalars(statement))
        rank = {
            FolderMappingScope.SECTION_DOCUMENT_TYPE: 60,
            FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE: 50,
            FolderMappingScope.SECTION: 40,
            FolderMappingScope.DEPARTMENT: 30,
            FolderMappingScope.DOCUMENT_TYPE: 20,
            FolderMappingScope.GLOBAL: 10,
        }

        def matches(profile: SharePointSyncProfile) -> bool:
            scope = profile.scope_type
            return {
                FolderMappingScope.GLOBAL: True,
                FolderMappingScope.DEPARTMENT: (
                    profile.department_id == department_id
                ),
                FolderMappingScope.SECTION: (
                    section_id is not None
                    and profile.section_id == section_id
                ),
                FolderMappingScope.DOCUMENT_TYPE: (
                    profile.document_type_id == document_type_id
                ),
                FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE: (
                    profile.department_id == department_id
                    and profile.document_type_id == document_type_id
                ),
                FolderMappingScope.SECTION_DOCUMENT_TYPE: (
                    section_id is not None
                    and profile.section_id == section_id
                    and profile.document_type_id == document_type_id
                ),
            }[scope]

        candidates = [profile for profile in profiles if matches(profile)]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda profile: (
                -rank[profile.scope_type],
                profile.name.casefold(),
                str(profile.id),
            ),
        )

    async def add_job(
        self,
        job: SharePointSyncJob,
    ) -> SharePointSyncJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(
        self,
        job_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> SharePointSyncJob | None:
        statement = select(SharePointSyncJob).where(
            SharePointSyncJob.id == job_id
        )
        if department_ids is not None:
            statement = statement.join(
                SharePointSyncProfile,
                SharePointSyncProfile.id
                == SharePointSyncJob.sync_profile_id,
            ).where(
                SharePointSyncProfile.department_id.in_(
                    list(department_ids)
                )
            )
        if for_update:
            statement = statement.with_for_update(of=SharePointSyncJob)
        return await self.session.scalar(statement)

    async def active_job(
        self,
        profile_id: UUID,
    ) -> SharePointSyncJob | None:
        return await self.session.scalar(
            select(SharePointSyncJob)
            .where(
                SharePointSyncJob.sync_profile_id == profile_id,
                SharePointSyncJob.status.in_(ACTIVE_SYNC_JOB_STATUSES),
            )
            .order_by(SharePointSyncJob.requested_at.desc())
            .limit(1)
        )

    async def scheduled_profiles_for_update(
        self,
        *,
        limit: int = 100,
    ) -> list[SharePointSyncProfile]:
        return list(
            await self.session.scalars(
                select(SharePointSyncProfile)
                .where(
                    SharePointSyncProfile.is_active.is_(True),
                    SharePointSyncProfile.sync_schedule.is_not(None),
                    func.length(
                        func.trim(SharePointSyncProfile.sync_schedule)
                    )
                    > 0,
                )
                .order_by(
                    SharePointSyncProfile.created_at.asc(),
                    SharePointSyncProfile.id.asc(),
                )
                .limit(limit)
                .with_for_update(
                    of=SharePointSyncProfile,
                    skip_locked=True,
                )
            )
        )

    async def latest_scheduled_job(
        self,
        profile_id: UUID,
    ) -> SharePointSyncJob | None:
        return await self.session.scalar(
            select(SharePointSyncJob)
            .where(
                SharePointSyncJob.sync_profile_id == profile_id,
                SharePointSyncJob.job_type.in_(
                    (
                        SyncJobType.SCHEDULED_FULL,
                        SyncJobType.SCHEDULED_INCREMENTAL,
                    )
                ),
            )
            .order_by(
                SharePointSyncJob.requested_at.desc(),
                SharePointSyncJob.id.desc(),
            )
            .limit(1)
        )

    async def list_jobs(
        self,
        *,
        department_ids: Sequence[UUID] | None,
        statuses: Sequence[SharePointSyncJobStatus] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointSyncJob], int]:
        base = select(SharePointSyncJob)
        if department_ids is not None:
            base = base.join(
                SharePointSyncProfile,
                SharePointSyncProfile.id
                == SharePointSyncJob.sync_profile_id,
            ).where(
                SharePointSyncProfile.department_id.in_(
                    list(department_ids)
                )
            )
        if statuses:
            base = base.where(
                SharePointSyncJob.status.in_(list(statuses))
            )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(SharePointSyncJob.requested_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def add_item(
        self,
        item: SharePointSyncItem,
    ) -> SharePointSyncItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_item(
        self,
        item_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointSyncItem | None:
        statement = select(SharePointSyncItem).where(
            SharePointSyncItem.id == item_id
        )
        if for_update:
            statement = statement.with_for_update(of=SharePointSyncItem)
        return await self.session.scalar(statement)

    async def get_item_by_idempotency(
        self,
        idempotency_key: str,
    ) -> SharePointSyncItem | None:
        return await self.session.scalar(
            select(SharePointSyncItem).where(
                SharePointSyncItem.idempotency_key == idempotency_key
            )
        )

    async def get_document_file_by_remote(
        self,
        *,
        drive_id: str,
        item_id: str,
    ) -> DocumentFile | None:
        return await self.session.scalar(
            select(DocumentFile)
            .where(
                DocumentFile.remote_drive_id == drive_id,
                DocumentFile.remote_item_id == item_id,
                DocumentFile.is_current.is_(True),
            )
            .order_by(DocumentFile.last_synced_at.desc())
            .limit(1)
        )

    async def list_profile_document_files(
        self,
        profile: SharePointSyncProfile,
        *,
        drive_id: str,
    ) -> list[DocumentFile]:
        """Return live current files eligible for one outbound profile."""

        statement = (
            self._profile_document_files_statement(
                profile,
                drive_id=drive_id,
            )
            .options(
                joinedload(DocumentFile.document),
                joinedload(DocumentFile.revision).joinedload(
                    DocumentRevision.document_status
                ),
            )
            .order_by(DocumentFile.uploaded_at.asc(), DocumentFile.id.asc())
        )
        return list(
            (await self.session.scalars(statement)).unique().all()
        )

    async def get_profile_revision_by_full_code(
        self,
        profile: SharePointSyncProfile,
        *,
        full_document_code: str,
    ) -> DocumentRevision | None:
        """Resolve an inbound filename only inside the configured scope."""

        statement = (
            select(DocumentRevision)
            .join(Document, Document.id == DocumentRevision.document_id)
            .where(
                DocumentRevision.full_document_code
                == full_document_code.strip(),
                DocumentRevision.deleted_at.is_(None),
                Document.deleted_at.is_(None),
                Document.is_archived.is_(False),
            )
            .options(joinedload(DocumentRevision.document))
        )
        scope_filter = self._profile_document_scope_filter(profile)
        if scope_filter is None and profile.scope_type is not FolderMappingScope.GLOBAL:
            return None
        if scope_filter is not None:
            statement = statement.where(scope_filter)
        return await self.session.scalar(statement)

    @classmethod
    def _profile_document_files_statement(
        cls,
        profile: SharePointSyncProfile,
        *,
        drive_id: str,
    ):
        statement = (
            select(DocumentFile)
            .join(Document, Document.id == DocumentFile.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id == DocumentFile.document_revision_id,
            )
            .where(
                DocumentFile.is_current.is_(True),
                DocumentFile.is_primary.is_(True),
                DocumentFile.deleted_at.is_(None),
                DocumentFile.file_status == DocumentFileStatus.AVAILABLE,
                DocumentRevision.is_current.is_(True),
                DocumentRevision.deleted_at.is_(None),
                Document.deleted_at.is_(None),
                Document.is_archived.is_(False),
                or_(
                    DocumentFile.sharepoint_connection_id.is_(None),
                    DocumentFile.sharepoint_connection_id
                    == profile.sharepoint_connection_id,
                ),
                or_(
                    DocumentFile.remote_drive_id.is_(None),
                    DocumentFile.remote_drive_id == drive_id,
                ),
            )
        )
        scope_filter = cls._profile_document_scope_filter(profile)
        if scope_filter is None and profile.scope_type is not FolderMappingScope.GLOBAL:
            return statement.where(False)
        if scope_filter is not None:
            statement = statement.where(scope_filter)
        return statement

    @staticmethod
    def _profile_document_scope_filter(
        profile: SharePointSyncProfile,
    ):
        scope = profile.scope_type
        if scope is FolderMappingScope.GLOBAL:
            return None
        if scope is FolderMappingScope.DEPARTMENT:
            return (
                Document.department_id == profile.department_id
                if profile.department_id is not None
                else None
            )
        if scope is FolderMappingScope.SECTION:
            return (
                Document.section_id == profile.section_id
                if profile.section_id is not None
                else None
            )
        if scope is FolderMappingScope.DOCUMENT_TYPE:
            return (
                Document.document_type_id == profile.document_type_id
                if profile.document_type_id is not None
                else None
            )
        if scope is FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE:
            if (
                profile.department_id is None
                or profile.document_type_id is None
            ):
                return None
            return (
                (Document.department_id == profile.department_id)
                & (
                    Document.document_type_id
                    == profile.document_type_id
                )
            )
        if scope is FolderMappingScope.SECTION_DOCUMENT_TYPE:
            if (
                profile.section_id is None
                or profile.document_type_id is None
            ):
                return None
            return (
                (Document.section_id == profile.section_id)
                & (
                    Document.document_type_id
                    == profile.document_type_id
                )
            )
        return None

    async def list_items(
        self,
        job_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointSyncItem], int]:
        base = select(SharePointSyncItem).where(
            SharePointSyncItem.sync_job_id == job_id
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(SharePointSyncItem.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def list_all_items(
        self,
        job_id: UUID,
    ) -> list[SharePointSyncItem]:
        return list(
            await self.session.scalars(
                select(SharePointSyncItem)
                .where(SharePointSyncItem.sync_job_id == job_id)
                .order_by(
                    SharePointSyncItem.created_at.asc(),
                    SharePointSyncItem.id.asc(),
                )
            )
        )

    async def get_delta_state(
        self,
        *,
        profile_id: UUID,
        drive_id: str,
        folder_item_id: str | None,
        for_update: bool = False,
    ) -> SharePointDeltaState | None:
        statement = select(SharePointDeltaState).where(
            SharePointDeltaState.sync_profile_id == profile_id,
            SharePointDeltaState.drive_id == drive_id,
            SharePointDeltaState.folder_item_id == folder_item_id,
        )
        if for_update:
            statement = statement.with_for_update(
                of=SharePointDeltaState
            )
        return await self.session.scalar(statement)

    async def add_delta_state(
        self,
        state: SharePointDeltaState,
    ) -> SharePointDeltaState:
        self.session.add(state)
        await self.session.flush()
        return state
