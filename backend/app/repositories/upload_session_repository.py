"""Persistence operations for upload-session lifecycles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.upload_session import UploadSession, UploadSessionStatus
from app.models.upload_session_item import UploadSessionItem


class UploadSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, upload_session: UploadSession) -> UploadSession:
        self.session.add(upload_session)
        await self.session.flush()
        return upload_session

    async def get_by_id(
        self,
        session_id: UUID,
        *,
        user_id: UUID | None = None,
        for_update: bool = False,
        with_items: bool = True,
    ) -> UploadSession | None:
        statement = select(UploadSession).where(
            UploadSession.id == session_id
        )
        if user_id is not None:
            statement = statement.where(UploadSession.user_id == user_id)
        if with_items:
            statement = statement.options(
                selectinload(UploadSession.items)
            )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def update_status(
        self,
        upload_session: UploadSession,
        status: UploadSessionStatus,
    ) -> UploadSession:
        upload_session.status = status
        await self.session.flush()
        return upload_session

    async def mark_committed(
        self,
        upload_session: UploadSession,
        *,
        status: UploadSessionStatus,
        committed_at: datetime,
    ) -> UploadSession:
        upload_session.status = status
        upload_session.committed_at = committed_at
        await self.session.flush()
        return upload_session

    async def mark_cancelled(
        self,
        upload_session: UploadSession,
        *,
        cancelled_at: datetime,
    ) -> UploadSession:
        upload_session.status = UploadSessionStatus.CANCELLED
        upload_session.cancelled_at = cancelled_at
        await self.session.flush()
        return upload_session

    async def find_expired(
        self,
        now: datetime,
        *,
        limit: int = 1000,
    ) -> list[UploadSession]:
        active_statuses = (
            UploadSessionStatus.CREATED,
            UploadSessionStatus.UPLOADING,
            UploadSessionStatus.READY_FOR_CONFIRMATION,
            UploadSessionStatus.FAILED,
        )
        terminal_statuses = (
            UploadSessionStatus.COMMITTED,
            UploadSessionStatus.PARTIALLY_COMMITTED,
            UploadSessionStatus.CANCELLED,
            UploadSessionStatus.EXPIRED,
        )
        has_pending_cleanup = UploadSession.items.any(
            UploadSessionItem.temporary_cleanup_pending.is_(True)
        )
        statement = (
            select(UploadSession)
            .where(
                or_(
                    and_(
                        UploadSession.expires_at <= now,
                        UploadSession.status.in_(active_statuses),
                    ),
                    and_(
                        UploadSession.status.in_(terminal_statuses),
                        has_pending_cleanup,
                    ),
                ),
            )
            .options(selectinload(UploadSession.items))
            .order_by(UploadSession.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self.session.scalars(statement)).unique().all())
