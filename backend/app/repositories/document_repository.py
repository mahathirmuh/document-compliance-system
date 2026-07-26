"""Database access for document identities and register queries."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models.department import Department
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.document_type import DocumentType


class DocumentRepository:
    """Persistence-only document operations with eager register loading."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _summary_options() -> tuple[ExecutableOption, ...]:
        current = selectinload(Document.current_revision)
        return (
            selectinload(Document.department),
            selectinload(Document.section),
            selectinload(Document.document_type),
            selectinload(Document.owner_department),
            current.selectinload(DocumentRevision.document_status),
            current.selectinload(DocumentRevision.validation_rule),
        )

    @classmethod
    def _detail_options(cls) -> tuple[ExecutableOption, ...]:
        revisions = selectinload(Document.revisions)
        return (
            *cls._summary_options(),
            selectinload(Document.creator),
            selectinload(Document.updater),
            selectinload(Document.archiver),
            revisions.selectinload(DocumentRevision.document_status),
            revisions.selectinload(DocumentRevision.validation_rule),
            revisions.selectinload(DocumentRevision.creator),
            revisions.selectinload(DocumentRevision.updater),
        )

    async def get_by_id(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
        detail: bool = False,
    ) -> Document | None:
        statement = (
            select(Document)
            .options(
                *(
                    self._detail_options()
                    if detail
                    else self._summary_options()
                )
            )
            .where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_detail(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
    ) -> Document | None:
        return await self.get_by_id(
            document_id,
            for_update=for_update,
            detail=True,
        )

    async def get_with_current_revision(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
    ) -> Document | None:
        return await self.get_by_id(
            document_id,
            for_update=for_update,
            detail=False,
        )

    async def get_by_base_code(
        self,
        base_document_code: str,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> Document | None:
        statement = select(Document).options(*self._summary_options()).where(
            Document.base_document_code == base_document_code.strip().upper()
        )
        if not include_deleted:
            statement = statement.where(Document.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_by_base_codes(
        self,
        base_document_codes: Sequence[str],
    ) -> list[Document]:
        if not base_document_codes:
            return []
        statement = (
            select(Document)
            .options(*self._summary_options())
            .where(
                Document.base_document_code.in_(
                    [
                        code.strip().upper()
                        for code in base_document_codes
                    ]
                ),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.id)
        )
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    async def lock_by_ids(
        self,
        document_ids: Sequence[UUID],
    ) -> list[Document]:
        """Lock documents in a stable UUID order across bulk workflows."""
        if not document_ids:
            return []
        statement = (
            select(Document)
            .options(*self._summary_options())
            .where(
                Document.id.in_(document_ids),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.id)
            .with_for_update()
        )
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    async def exists_by_base_code(
        self,
        base_document_code: str,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        statement = select(Document.id).where(
            Document.base_document_code
            == base_document_code.strip().upper(),
            Document.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Document.id != exclude_id)
        return (await self.session.scalar(statement)) is not None

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def update(self, document: Document) -> Document:
        await self.session.flush()
        return document

    async def archive(
        self,
        document: Document,
        *,
        archived_at: datetime,
        archived_by: UUID,
        reason: str,
    ) -> Document:
        document.is_archived = True
        document.archived_at = archived_at
        document.archived_by = archived_by
        document.archive_reason = reason
        await self.session.flush()
        return document

    async def restore(self, document: Document) -> Document:
        document.is_archived = False
        document.archived_at = None
        document.archived_by = None
        document.archive_reason = None
        await self.session.flush()
        return document

    async def list(
        self,
        *,
        search: str | None = None,
        base_document_code: str | None = None,
        department_id: UUID | None = None,
        section_id: UUID | None = None,
        document_type_id: UUID | None = None,
        document_status_id: UUID | None = None,
        validation_rule_id: UUID | None = None,
        revision_code: str | None = None,
        company_code: str | None = None,
        is_archived: bool = False,
        has_sharepoint_url: bool | None = None,
        created_by: UUID | None = None,
        created_from_utc: datetime | None = None,
        created_to_utc_exclusive: datetime | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        scope_all_departments: bool = False,
        scope_department_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updatedAt",
        sort_order: str = "desc",
    ) -> tuple[list[Document], int]:
        current = aliased(DocumentRevision)
        department = aliased(Department)
        document_type = aliased(DocumentType)
        statement = (
            select(Document)
            .outerjoin(current, Document.current_revision_id == current.id)
            .join(department, Document.department_id == department.id)
            .join(
                document_type,
                Document.document_type_id == document_type.id,
            )
            .options(*self._summary_options())
            .where(
                Document.deleted_at.is_(None),
                Document.is_archived.is_(is_archived),
            )
        )
        if not scope_all_departments:
            if scope_department_id is None:
                statement = statement.where(false())
            else:
                statement = statement.where(
                    Document.department_id == scope_department_id
                )
        if base_document_code:
            statement = statement.where(
                Document.base_document_code
                == base_document_code.strip().upper()
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Document.base_document_code.ilike(pattern),
                    current.full_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    Document.document_number.ilike(pattern),
                    Document.document_owner_name.ilike(pattern),
                    current.external_reference.ilike(pattern),
                )
            )
        if department_id is not None:
            statement = statement.where(
                Document.department_id == department_id
            )
        if section_id is not None:
            statement = statement.where(Document.section_id == section_id)
        if document_type_id is not None:
            statement = statement.where(
                Document.document_type_id == document_type_id
            )
        if document_status_id is not None:
            statement = statement.where(
                current.document_status_id == document_status_id
            )
        if validation_rule_id is not None:
            statement = statement.where(
                current.validation_rule_id == validation_rule_id
            )
        if revision_code:
            statement = statement.where(
                current.revision_code
                == revision_code.strip()
            )
        if company_code:
            statement = statement.where(
                Document.company_code == company_code.strip().upper()
            )
        if has_sharepoint_url is True:
            statement = statement.where(
                current.sharepoint_url.is_not(None),
                current.sharepoint_url != "",
            )
        elif has_sharepoint_url is False:
            statement = statement.where(
                or_(
                    current.id.is_(None),
                    current.sharepoint_url.is_(None),
                    current.sharepoint_url == "",
                )
            )
        if created_by is not None:
            statement = statement.where(Document.created_by == created_by)
        if created_from_utc is not None:
            statement = statement.where(
                Document.created_at >= created_from_utc
            )
        if created_to_utc_exclusive is not None:
            statement = statement.where(
                Document.created_at < created_to_utc_exclusive
            )
        if effective_from is not None:
            statement = statement.where(
                current.effective_date >= effective_from
            )
        if effective_to is not None:
            statement = statement.where(
                current.effective_date <= effective_to
            )

        count_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total = int((await self.session.scalar(count_statement)) or 0)
        sort_columns = {
            "baseDocumentCode": Document.base_document_code,
            "title": Document.title,
            "companyCode": Document.company_code,
            "department": department.code,
            "documentType": document_type.code,
            "createdAt": Document.created_at,
            "updatedAt": Document.updated_at,
            "effectiveDate": current.effective_date,
        }
        sort_column = sort_columns.get(sort_by, Document.updated_at)
        ordering = desc(sort_column) if sort_order == "desc" else asc(sort_column)
        result = await self.session.scalars(
            statement.order_by(ordering, asc(Document.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def count(self, **filters: Any) -> int:
        _, total = await self.list(page=1, page_size=1, **filters)
        return total
