"""Persistence operations for physical document files."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision


class DocumentFileRepository:
    """Database-only file queries; business policy stays in services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(DocumentFile.document),
            joinedload(DocumentFile.revision).joinedload(
                DocumentRevision.document_status
            ),
            joinedload(DocumentFile.uploader),
            joinedload(DocumentFile.deleter),
        )

    async def create(self, document_file: DocumentFile) -> DocumentFile:
        self.session.add(document_file)
        await self.session.flush()
        return document_file

    async def get_by_id(
        self,
        file_id: UUID,
        *,
        for_update: bool = False,
    ) -> DocumentFile | None:
        statement = (
            select(DocumentFile)
            .where(DocumentFile.id == file_id)
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(
                of=DocumentFile
            ).execution_options(populate_existing=True)
        return await self.session.scalar(statement)

    async def list_by_document(
        self,
        document_id: UUID,
        *,
        include_deleted: bool = True,
    ) -> list[DocumentFile]:
        statement = (
            select(DocumentFile)
            .where(DocumentFile.document_id == document_id)
            .options(*self._options())
            .order_by(DocumentFile.uploaded_at.desc(), DocumentFile.id.desc())
        )
        if not include_deleted:
            statement = statement.where(
                DocumentFile.file_status != DocumentFileStatus.DELETED
            )
        return list((await self.session.scalars(statement)).unique().all())

    async def list_by_revision(
        self,
        revision_id: UUID,
        *,
        include_deleted: bool = True,
    ) -> list[DocumentFile]:
        statement = (
            select(DocumentFile)
            .where(DocumentFile.document_revision_id == revision_id)
            .options(*self._options())
            .order_by(DocumentFile.uploaded_at.desc(), DocumentFile.id.desc())
        )
        if not include_deleted:
            statement = statement.where(
                DocumentFile.file_status != DocumentFileStatus.DELETED
            )
        return list((await self.session.scalars(statement)).unique().all())

    async def get_current_by_revision(
        self,
        revision_id: UUID,
        *,
        for_update: bool = False,
    ) -> DocumentFile | None:
        statement = (
            select(DocumentFile)
            .where(
                DocumentFile.document_revision_id == revision_id,
                DocumentFile.is_primary.is_(True),
                DocumentFile.is_current.is_(True),
                DocumentFile.file_status == DocumentFileStatus.AVAILABLE,
            )
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(
                of=DocumentFile
            ).execution_options(populate_existing=True)
        return await self.session.scalar(statement)

    async def find_by_hash(
        self,
        sha256_hash: str,
        file_size: int,
    ) -> list[DocumentFile]:
        statement = (
            select(DocumentFile)
            .where(
                DocumentFile.sha256_hash == sha256_hash.lower(),
                DocumentFile.file_size == file_size,
                DocumentFile.file_status.in_(
                    (
                        DocumentFileStatus.AVAILABLE,
                        DocumentFileStatus.REPLACED,
                        DocumentFileStatus.DELETED,
                    )
                ),
            )
            .options(*self._options())
            .order_by(DocumentFile.uploaded_at.desc())
        )
        return list((await self.session.scalars(statement)).unique().all())

    async def clear_current(
        self,
        revision_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        statement = update(DocumentFile).where(
            DocumentFile.document_revision_id == revision_id,
            DocumentFile.is_primary.is_(True),
            DocumentFile.is_current.is_(True),
        )
        if exclude_id is not None:
            statement = statement.where(DocumentFile.id != exclude_id)
        await self.session.execute(statement.values(is_current=False))
        await self.session.flush()

    async def mark_replaced(
        self,
        old_file: DocumentFile,
        *,
        replacement_id: UUID,
        replaced_at: datetime,
    ) -> DocumentFile:
        old_file.is_current = False
        old_file.file_status = DocumentFileStatus.REPLACED
        old_file.replaced_at = replaced_at
        old_file.replaced_by_file_id = replacement_id
        await self.session.flush()
        return old_file

    async def prepare_replacement(
        self,
        old_file: DocumentFile,
        *,
        replaced_at: datetime,
    ) -> DocumentFile:
        """Release the partial-current constraint before inserting a new row."""
        old_file.is_current = False
        old_file.file_status = DocumentFileStatus.REPLACED
        old_file.replaced_at = replaced_at
        old_file.replaced_by_file_id = None
        await self.session.flush()
        return old_file

    async def link_replacement(
        self,
        old_file: DocumentFile,
        *,
        replacement_id: UUID,
    ) -> DocumentFile:
        """Link only after the replacement row satisfies its foreign key."""
        old_file.replaced_by_file_id = replacement_id
        await self.session.flush()
        return old_file

    async def soft_delete(
        self,
        document_file: DocumentFile,
        *,
        deleted_at: datetime,
        deleted_by: UUID,
        reason: str,
    ) -> DocumentFile:
        document_file.is_current = False
        document_file.file_status = DocumentFileStatus.DELETED
        document_file.deleted_at = deleted_at
        document_file.deleted_by = deleted_by
        document_file.deletion_reason = reason
        await self.session.flush()
        return document_file

    async def restore(
        self,
        document_file: DocumentFile,
        *,
        is_current: bool,
    ) -> DocumentFile:
        document_file.file_status = DocumentFileStatus.AVAILABLE
        document_file.is_current = is_current
        document_file.replaced_at = None
        document_file.replaced_by_file_id = None
        document_file.deleted_at = None
        document_file.deleted_by = None
        document_file.deletion_reason = None
        await self.session.flush()
        return document_file

    async def list_history(
        self,
        *,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        department_id: UUID | None = None,
        uploaded_by: UUID | None = None,
        file_status: DocumentFileStatus | None = None,
        file_extension: str | None = None,
        uploaded_from: datetime | None = None,
        uploaded_to: datetime | None = None,
        search: str | None = None,
        scope_all_departments: bool = False,
        scope_department_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DocumentFile], int]:
        predicates: list[object] = []
        if document_id is not None:
            predicates.append(DocumentFile.document_id == document_id)
        if revision_id is not None:
            predicates.append(
                DocumentFile.document_revision_id == revision_id
            )
        if department_id is not None:
            predicates.append(Document.department_id == department_id)
        if uploaded_by is not None:
            predicates.append(DocumentFile.uploaded_by == uploaded_by)
        if file_status is not None:
            predicates.append(DocumentFile.file_status == file_status)
        if file_extension is not None:
            predicates.append(
                DocumentFile.file_extension == file_extension.lower()
            )
        if uploaded_from is not None:
            predicates.append(DocumentFile.uploaded_at >= uploaded_from)
        if uploaded_to is not None:
            predicates.append(DocumentFile.uploaded_at < uploaded_to)
        if not scope_all_departments:
            predicates.append(
                Document.department_id == scope_department_id
                if scope_department_id is not None
                else false()
            )
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            predicates.append(
                or_(
                    func.lower(DocumentFile.original_filename).like(pattern),
                    func.lower(Document.base_document_code).like(pattern),
                    func.lower(Document.title).like(pattern),
                    func.lower(DocumentRevision.full_document_code).like(
                        pattern
                    ),
                )
            )
        base = (
            select(DocumentFile)
            .join(Document, Document.id == DocumentFile.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id
                == DocumentFile.document_revision_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            base.options(*self._options())
            .order_by(DocumentFile.uploaded_at.desc(), DocumentFile.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(
            (await self.session.scalars(statement)).unique().all()
        )
        return items, total
