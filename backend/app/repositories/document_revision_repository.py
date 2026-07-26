"""Database access for document revision history."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models.document_revision import DocumentRevision


class DocumentRevisionRepository:
    """Persistence-only revision operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[ExecutableOption, ...]:
        return (
            selectinload(DocumentRevision.document_status),
            selectinload(DocumentRevision.validation_rule),
            selectinload(DocumentRevision.creator),
            selectinload(DocumentRevision.updater),
        )

    async def get_by_id(
        self,
        revision_id: UUID,
        *,
        document_id: UUID | None = None,
        for_update: bool = False,
    ) -> DocumentRevision | None:
        statement = (
            select(DocumentRevision)
            .options(*self._options())
            .where(
                DocumentRevision.id == revision_id,
                DocumentRevision.deleted_at.is_(None),
            )
        )
        if document_id is not None:
            statement = statement.where(
                DocumentRevision.document_id == document_id
            )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_document_and_code(
        self,
        document_id: UUID,
        revision_code: str,
        *,
        for_update: bool = False,
    ) -> DocumentRevision | None:
        statement = (
            select(DocumentRevision)
            .options(*self._options())
            .where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.revision_code == revision_code.strip(),
                DocumentRevision.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_full_code(
        self,
        full_document_code: str,
        *,
        for_update: bool = False,
    ) -> DocumentRevision | None:
        """Resolve one live revision by its globally unique full code."""
        statement = (
            select(DocumentRevision)
            .options(*self._options())
            .where(
                DocumentRevision.full_document_code
                == full_document_code.strip(),
                DocumentRevision.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_by_document_codes(
        self,
        keys: Sequence[tuple[UUID, str]],
        *,
        for_update: bool = False,
    ) -> list[DocumentRevision]:
        if not keys:
            return []
        statement = (
            select(DocumentRevision)
            .options(*self._options())
            .where(
                tuple_(
                    DocumentRevision.document_id,
                    DocumentRevision.revision_code,
                ).in_(keys),
                DocumentRevision.deleted_at.is_(None),
            )
            .order_by(
                DocumentRevision.document_id,
                DocumentRevision.revision_code,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    async def list_by_document(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[DocumentRevision]:
        statement = (
            select(DocumentRevision)
            .options(*self._options())
            .where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.deleted_at.is_(None),
            )
            .order_by(
                DocumentRevision.revision_number.desc().nullslast(),
                DocumentRevision.created_at.desc(),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    async def create(
        self,
        revision: DocumentRevision,
    ) -> DocumentRevision:
        self.session.add(revision)
        await self.session.flush()
        return revision

    async def update(
        self,
        revision: DocumentRevision,
    ) -> DocumentRevision:
        await self.session.flush()
        return revision

    async def clear_current(
        self,
        document_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        statement = (
            update(DocumentRevision)
            .where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.is_current.is_(True),
                DocumentRevision.deleted_at.is_(None),
            )
            .values(is_current=False)
        )
        if exclude_id is not None:
            statement = statement.where(
                DocumentRevision.id != exclude_id
            )
        await self.session.execute(statement)
        await self.session.flush()

    async def set_current(
        self,
        revision: DocumentRevision,
    ) -> DocumentRevision:
        await self.clear_current(
            revision.document_id,
            exclude_id=revision.id,
        )
        revision.is_current = True
        await self.session.flush()
        return revision

    async def mark_superseded(
        self,
        revision: DocumentRevision,
        *,
        superseded_at: datetime,
        superseded_by_revision_id: UUID,
    ) -> DocumentRevision:
        revision.is_superseded = True
        revision.superseded_at = superseded_at
        revision.superseded_by_revision_id = superseded_by_revision_id
        await self.session.flush()
        return revision

    async def exists_by_full_code(
        self,
        full_document_code: str,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        statement = select(DocumentRevision.id).where(
            DocumentRevision.full_document_code
            == full_document_code.strip(),
            DocumentRevision.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(
                DocumentRevision.id != exclude_id
            )
        return (await self.session.scalar(statement)) is not None
