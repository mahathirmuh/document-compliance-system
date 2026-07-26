"""Persistence operations for files staged in upload sessions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
    UploadSessionItem,
    UploadSessionItemStatus,
)


class UploadSessionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[ExecutableOption, ...]:
        return (
            joinedload(UploadSessionItem.matched_document),
            joinedload(UploadSessionItem.matched_revision),
        )

    async def create(self, item: UploadSessionItem) -> UploadSessionItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(
        self,
        item_id: UUID,
        *,
        session_id: UUID | None = None,
        for_update: bool = False,
    ) -> UploadSessionItem | None:
        statement = (
            select(UploadSessionItem)
            .where(UploadSessionItem.id == item_id)
            .options(*self._options())
        )
        if session_id is not None:
            statement = statement.where(
                UploadSessionItem.upload_session_id == session_id
            )
        if for_update:
            statement = statement.with_for_update(of=UploadSessionItem)
        return await self.session.scalar(statement)

    async def list_by_session(
        self,
        session_id: UUID,
    ) -> list[UploadSessionItem]:
        statement = (
            select(UploadSessionItem)
            .where(UploadSessionItem.upload_session_id == session_id)
            .options(*self._options())
            .order_by(UploadSessionItem.created_at, UploadSessionItem.id)
        )
        return list((await self.session.scalars(statement)).unique().all())

    async def update_identification(
        self,
        item: UploadSessionItem,
        *,
        identification_status: UploadIdentificationStatus,
        proposed_action: UploadProposedAction,
        matched_document_id: UUID | None,
        matched_revision_id: UUID | None,
        parsed_metadata: dict[str, object] | None,
        warnings: list[str],
        errors: list[str],
        status: UploadSessionItemStatus,
    ) -> UploadSessionItem:
        item.identification_status = identification_status
        item.proposed_action = proposed_action
        item.matched_document_id = matched_document_id
        item.matched_revision_id = matched_revision_id
        item.parsed_metadata_json = parsed_metadata
        item.warnings_json = warnings
        item.errors_json = errors
        item.status = status
        await self.session.flush()
        return item

    async def update_status(
        self,
        item: UploadSessionItem,
        status: UploadSessionItemStatus,
    ) -> UploadSessionItem:
        item.status = status
        await self.session.flush()
        return item
