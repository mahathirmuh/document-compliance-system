"""Idempotent cleanup of expired and residual two-stage upload objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.upload_session import UploadSessionStatus
from app.models.upload_session_item import (
    UploadSessionItem,
    UploadSessionItemStatus,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.upload_session_repository import (
    UploadSessionRepository,
)
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_factory import StorageFactory
from app.utils.datetime import utc_now


@dataclass(frozen=True, slots=True)
class UploadCleanupSummary:
    scanned_sessions: int
    expired_sessions: int
    deleted_files: int
    failed_sessions: int


class UploadCleanupService:
    """Remove expired temporary objects and retain auditable session rows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: BaseStorage | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or StorageFactory.get_storage()
        self.sessions = UploadSessionRepository(session)
        self.audit_logs = AuditLogRepository(session)

    async def cleanup_expired(
        self,
        *,
        now: datetime | None = None,
        limit: int = 1000,
        commit: bool = True,
    ) -> UploadCleanupSummary:
        if limit <= 0:
            raise ValueError("limit must be positive.")
        if not commit:
            raise ValueError(
                "Upload cleanup must commit database state before deleting "
                "storage objects."
            )
        cleanup_time = now or utc_now()
        expired = await self.sessions.find_expired(
            cleanup_time,
            limit=limit,
        )
        expired_sessions = 0
        pending_items: list[list[UploadSessionItem]] = []

        for upload_session in expired:
            cleanup_items = [
                item
                for item in upload_session.items
                if item.temporary_cleanup_pending
            ]
            pending_items.append(cleanup_items)
            if upload_session.status in {
                UploadSessionStatus.CREATED,
                UploadSessionStatus.UPLOADING,
                UploadSessionStatus.READY_FOR_CONFIRMATION,
                UploadSessionStatus.FAILED,
            }:
                for item in upload_session.items:
                    if item.status not in {
                        UploadSessionItemStatus.COMMITTED,
                        UploadSessionItemStatus.SKIPPED,
                    }:
                        item.status = UploadSessionItemStatus.CANCELLED

                upload_session.status = UploadSessionStatus.EXPIRED
                await self.audit_logs.create(
                    action=AuditAction.CLEANUP_EXPIRED_UPLOAD_SESSION,
                    user_id=None,
                    entity_type="upload_session",
                    entity_id=upload_session.id,
                    description=(
                        "Expired a temporary upload session and scheduled "
                        "its residual objects for cleanup."
                    ),
                    new_values={
                        "sessionId": str(upload_session.id),
                        "temporaryFilesScheduled": len(cleanup_items),
                        "expiredAt": cleanup_time.isoformat(),
                    },
                )
                expired_sessions += 1

        # Persist terminal state before any irreversible storage deletion.
        await self.session.commit()

        deleted_files = 0
        failed_sessions = 0
        for _upload_session, cleanup_items in zip(
            expired,
            pending_items,
            strict=True,
        ):
            session_failed = False
            cleaned_items = []
            for item in cleanup_items:
                try:
                    await self.storage.delete(item.temporary_storage_key)
                except Exception:  # noqa: BLE001
                    session_failed = True
                    continue
                item.temporary_cleanup_pending = False
                cleaned_items.append(item)
                deleted_files += 1
            if cleaned_items:
                await self.session.commit()
            if session_failed:
                failed_sessions += 1

        return UploadCleanupSummary(
            scanned_sessions=len(expired),
            expired_sessions=expired_sessions,
            deleted_files=deleted_files,
            failed_sessions=failed_sessions,
        )
