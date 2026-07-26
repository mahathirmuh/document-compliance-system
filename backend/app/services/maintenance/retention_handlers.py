"""Concrete, scoped retention handlers for scheduled maintenance tasks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_retention_policy import (
    DataRetentionPolicy,
    RetentionEntityType,
    RetentionScopeType,
)
from app.models.dead_letter_job import DeadLetterJob
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.graph_webhook_event import GraphWebhookEvent
from app.models.in_app_notification import InAppNotification
from app.models.report_snapshot import (
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.models.sharepoint_enums import (
    DeadLetterStatus,
    GraphWebhookProcessingStatus,
)
from app.models.upload_session import UploadSession, UploadSessionStatus
from app.models.upload_session_item import (
    UploadSessionItemStatus,
)
from app.models.user import User
from app.services.retention.contracts import (
    RetentionCandidate,
    RetentionEntityHandler,
)
from app.services.storage.base_storage import BaseStorage
from app.utils.datetime import utc_now

_TERMINAL_WEBHOOK_STATUSES = (
    GraphWebhookProcessingStatus.PROCESSED,
    GraphWebhookProcessingStatus.IGNORED,
    GraphWebhookProcessingStatus.FAILED,
    GraphWebhookProcessingStatus.DUPLICATE,
)
_TERMINAL_REPORT_JOBS = (
    ReportJobStatus.COMPLETED,
    ReportJobStatus.FAILED,
    ReportJobStatus.CANCELLED,
)


def _selection_cutoff(
    archive_cutoff: datetime | None,
    delete_cutoff: datetime,
) -> datetime:
    return max(item for item in (archive_cutoff, delete_cutoff) if item is not None)


def _legal_hold(metadata: dict[str, object] | None) -> bool:
    value = metadata or {}
    return bool(value.get("legalHold") or value.get("legal_hold"))


class InAppNotificationRetentionHandler:
    supports_archive = False
    supports_soft_delete = True

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        if policy.scope_type != RetentionScopeType.GLOBAL:
            return []
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        rows = list(
            await self.session.scalars(
                select(InAppNotification)
                .where(InAppNotification.created_at <= cutoff)
                .order_by(InAppNotification.created_at.asc())
                .limit(limit)
            )
        )
        return [
            RetentionCandidate(
                id=row.id,
                created_at=row.created_at,
                soft_deleted=row.dismissed_at is not None,
            )
            for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        row = await self.session.get(InAppNotification, candidate.id)
        if row is not None and row.dismissed_at is None:
            row.dismissed_at = utc_now()

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self.session.get(InAppNotification, candidate.id)
        if row is not None:
            await self.session.delete(row)


class GraphWebhookEventRetentionHandler:
    supports_archive = False
    supports_soft_delete = False

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        if policy.scope_type != RetentionScopeType.GLOBAL:
            return []
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        rows = list(
            await self.session.scalars(
                select(GraphWebhookEvent)
                .where(
                    GraphWebhookEvent.created_at <= cutoff,
                    GraphWebhookEvent.processing_status.in_(_TERMINAL_WEBHOOK_STATUSES),
                )
                .order_by(GraphWebhookEvent.created_at.asc())
                .limit(limit)
            )
        )
        return [
            RetentionCandidate(id=row.id, created_at=row.created_at) for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self.session.get(GraphWebhookEvent, candidate.id)
        if row is not None:
            await self.session.delete(row)


class DeadLetterJobRetentionHandler:
    supports_archive = False
    supports_soft_delete = True

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        if policy.scope_type != RetentionScopeType.GLOBAL:
            return []
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        rows = list(
            await self.session.scalars(
                select(DeadLetterJob)
                .where(DeadLetterJob.created_at <= cutoff)
                .order_by(DeadLetterJob.created_at.asc())
                .limit(limit)
            )
        )
        return [
            RetentionCandidate(
                id=row.id,
                created_at=row.created_at,
                soft_deleted=row.status == DeadLetterStatus.DISMISSED,
            )
            for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        row = await self.session.get(DeadLetterJob, candidate.id)
        if row is not None:
            row.status = DeadLetterStatus.DISMISSED
            row.dismissed_at = utc_now()
            row.dismissal_reason = "Dismissed by approved retention policy."

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self.session.get(DeadLetterJob, candidate.id)
        if row is not None:
            await self.session.delete(row)


class ReportSnapshotRetentionHandler:
    supports_archive = True
    supports_soft_delete = True

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: BaseStorage,
    ) -> None:
        self.session = session
        self.storage = storage

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        if policy.scope_type not in {
            RetentionScopeType.GLOBAL,
            RetentionScopeType.DEPARTMENT,
        }:
            return []
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        statement = select(ReportSnapshot).where(ReportSnapshot.created_at <= cutoff)
        if policy.scope_type == RetentionScopeType.DEPARTMENT:
            statement = statement.where(
                ReportSnapshot.scope_department_id == policy.department_id
            )
        rows = list(
            await self.session.scalars(
                statement.order_by(ReportSnapshot.created_at.asc()).limit(limit)
            )
        )
        return [
            RetentionCandidate(
                id=row.id,
                created_at=row.created_at,
                legal_hold=_legal_hold(row.metadata_json),
                archived=row.status == ReportSnapshotStatus.EXPIRED,
                soft_deleted=row.status == ReportSnapshotStatus.DELETED,
            )
            for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        row = await self.session.get(ReportSnapshot, candidate.id)
        if row is None or row.status == ReportSnapshotStatus.DELETED:
            return
        row.status = ReportSnapshotStatus.EXPIRED
        row.metadata_json = {
            **row.metadata_json,
            "retentionArchivedAt": utc_now().isoformat(),
        }

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        row = await self.session.get(ReportSnapshot, candidate.id)
        if row is None:
            return
        row.status = ReportSnapshotStatus.DELETED
        if row.job_status not in _TERMINAL_REPORT_JOBS:
            row.job_status = ReportJobStatus.CANCELLED
            row.current_stage = "Deleted by retention policy"
        row.metadata_json = {
            **row.metadata_json,
            "retentionSoftDeletedAt": utc_now().isoformat(),
        }

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self.session.get(ReportSnapshot, candidate.id)
        if row is None:
            return
        if row.storage_key and await self.storage.exists(row.storage_key):
            await self.storage.delete(row.storage_key)
        await self.session.delete(row)


class TemporaryUploadRetentionHandler:
    supports_archive = False
    supports_soft_delete = True

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: BaseStorage,
    ) -> None:
        self.session = session
        self.storage = storage

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        if policy.scope_type not in {
            RetentionScopeType.GLOBAL,
            RetentionScopeType.DEPARTMENT,
        }:
            return []
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        statement = (
            select(UploadSession)
            .where(UploadSession.created_at <= cutoff)
            .options(selectinload(UploadSession.items))
        )
        if policy.scope_type == RetentionScopeType.DEPARTMENT:
            statement = statement.join(
                User,
                UploadSession.user_id == User.id,
            ).where(User.department_id == policy.department_id)
        rows = list(
            (
                await self.session.scalars(
                    statement.order_by(UploadSession.created_at.asc()).limit(limit)
                )
            )
            .unique()
            .all()
        )
        return [
            RetentionCandidate(
                id=row.id,
                created_at=row.created_at,
                soft_deleted=(
                    row.status == UploadSessionStatus.EXPIRED
                    and not any(item.temporary_cleanup_pending for item in row.items)
                ),
            )
            for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        row = await self._row(candidate.id)
        if row is None:
            return
        await self._delete_temporary_objects(row)
        for item in row.items:
            if item.status not in {
                UploadSessionItemStatus.COMMITTED,
                UploadSessionItemStatus.SKIPPED,
            }:
                item.status = UploadSessionItemStatus.CANCELLED
        row.status = UploadSessionStatus.EXPIRED

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self._row(candidate.id)
        if row is None:
            return
        await self._delete_temporary_objects(row)
        await self.session.delete(row)

    async def _row(self, row_id: UUID) -> UploadSession | None:
        return await self.session.scalar(
            select(UploadSession)
            .where(UploadSession.id == row_id)
            .options(selectinload(UploadSession.items))
        )

    async def _delete_temporary_objects(self, row: UploadSession) -> None:
        for item in row.items:
            if not item.temporary_cleanup_pending:
                continue
            if await self.storage.exists(item.temporary_storage_key):
                await self.storage.delete(item.temporary_storage_key)
            item.temporary_cleanup_pending = False


class DeletedDocumentFileRetentionHandler:
    supports_archive = False
    supports_soft_delete = True

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: BaseStorage,
    ) -> None:
        self.session = session
        self.storage = storage

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> list[RetentionCandidate]:
        cutoff = _selection_cutoff(archive_cutoff, delete_cutoff)
        statement = (
            select(DocumentFile)
            .join(Document, DocumentFile.document_id == Document.id)
            .where(
                DocumentFile.deleted_at.is_not(None),
                DocumentFile.deleted_at <= cutoff,
                DocumentFile.file_status == DocumentFileStatus.DELETED,
            )
        )
        if policy.scope_type in {
            RetentionScopeType.DEPARTMENT,
            RetentionScopeType.DEPARTMENT_DOCUMENT_TYPE,
        }:
            statement = statement.where(Document.department_id == policy.department_id)
        if policy.scope_type in {
            RetentionScopeType.DOCUMENT_TYPE,
            RetentionScopeType.DEPARTMENT_DOCUMENT_TYPE,
        }:
            statement = statement.where(
                Document.document_type_id == policy.document_type_id
            )
        rows = list(
            await self.session.scalars(
                statement.order_by(DocumentFile.deleted_at.asc()).limit(limit)
            )
        )
        active_counts = await self._active_file_counts(
            {row.document_revision_id for row in rows}
        )
        return [
            RetentionCandidate(
                id=row.id,
                created_at=row.deleted_at or row.uploaded_at,
                legal_hold=_legal_hold(row.metadata_json),
                soft_deleted=True,
                sole_copy=active_counts.get(row.document_revision_id, 0) == 0,
            )
            for row in rows
        ]

    async def archive(self, candidate: RetentionCandidate) -> None:
        del candidate

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        row = await self.session.get(DocumentFile, candidate.id)
        if row is not None and row.deleted_at is None:
            row.deleted_at = utc_now()
            row.file_status = DocumentFileStatus.DELETED
            row.is_current = False

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        row = await self.session.get(DocumentFile, candidate.id)
        if row is None:
            return
        if await self.storage.exists(row.storage_key):
            await self.storage.delete(row.storage_key)
        await self.session.delete(row)

    async def _active_file_counts(
        self,
        revision_ids: set[UUID],
    ) -> dict[UUID, int]:
        if not revision_ids:
            return {}
        rows = await self.session.execute(
            select(
                DocumentFile.document_revision_id,
                func.count(DocumentFile.id),
            )
            .where(
                DocumentFile.document_revision_id.in_(revision_ids),
                DocumentFile.deleted_at.is_(None),
                DocumentFile.file_status != DocumentFileStatus.DELETED,
            )
            .group_by(DocumentFile.document_revision_id)
        )
        return {revision_id: int(count) for revision_id, count in rows.all()}


def create_default_retention_handlers(
    session: AsyncSession,
    *,
    storage: BaseStorage,
) -> dict[RetentionEntityType, RetentionEntityHandler]:
    return {
        RetentionEntityType.TEMP_UPLOAD: TemporaryUploadRetentionHandler(
            session,
            storage=storage,
        ),
        RetentionEntityType.REPORT_SNAPSHOT: ReportSnapshotRetentionHandler(
            session,
            storage=storage,
        ),
        RetentionEntityType.NOTIFICATION: InAppNotificationRetentionHandler(session),
        RetentionEntityType.WEBHOOK_EVENT: GraphWebhookEventRetentionHandler(session),
        RetentionEntityType.JOB_LOG: DeadLetterJobRetentionHandler(session),
        RetentionEntityType.DELETED_FILE: (
            DeletedDocumentFileRetentionHandler(
                session,
                storage=storage,
            )
        ),
    }
