"""Database access for audited glossary exceptions."""

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.glossary_enums import (
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
)
from app.models.glossary_exception import GlossaryException
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_term import GlossaryTerm


class GlossaryExceptionRepository:
    """Persistence queries with department visibility filtering."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(GlossaryException).options(
            joinedload(GlossaryException.term).joinedload(
                GlossaryTerm.profile
            )
        )

    async def add(self, item: GlossaryException) -> GlossaryException:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(
        self,
        exception_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryException | None:
        statement = self.base_statement().where(
            GlossaryException.id == exception_id
        )
        statement = self._scope_to_departments(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryException
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        term_id: UUID | None = None,
        scope_type: GlossaryExceptionScopeType | None = None,
        exception_type: GlossaryExceptionType | None = None,
        language_code: GlossaryLanguageCode | None = None,
        is_active: bool | None = None,
        effective_on: date | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_order: str = "desc",
    ) -> tuple[list[GlossaryException], int]:
        statement = self.base_statement()
        statement = self._scope_to_departments(statement, department_ids)
        if term_id is not None:
            statement = statement.where(
                GlossaryException.glossary_term_id == term_id
            )
        if scope_type is not None:
            statement = statement.where(
                GlossaryException.scope_type == scope_type
            )
        if exception_type is not None:
            statement = statement.where(
                GlossaryException.exception_type == exception_type
            )
        if language_code is not None:
            statement = statement.where(
                GlossaryException.language_code == language_code
            )
        if is_active is not None:
            statement = statement.where(
                GlossaryException.is_active.is_(is_active)
            )
        if effective_on is not None:
            statement = statement.where(
                or_(
                    GlossaryException.effective_from.is_(None),
                    GlossaryException.effective_from <= effective_on,
                ),
                or_(
                    GlossaryException.effective_to.is_(None),
                    GlossaryException.effective_to >= effective_on,
                ),
            )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        order = (
            asc(GlossaryException.created_at)
            if sort_order == "asc"
            else desc(GlossaryException.created_at)
        )
        result = await self.session.scalars(
            statement.order_by(order, GlossaryException.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def list_for_terms(
        self,
        term_ids: Sequence[UUID],
        *,
        department_ids: Sequence[UUID] | None = None,
        include_inactive: bool = False,
    ) -> list[GlossaryException]:
        if not term_ids:
            return []
        statement = self.base_statement().where(
            GlossaryException.glossary_term_id.in_(list(term_ids))
        )
        statement = self._scope_to_departments(statement, department_ids)
        if not include_inactive:
            statement = statement.where(
                GlossaryException.is_active.is_(True)
            )
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    @staticmethod
    def _scope_to_departments(statement, department_ids):
        if department_ids is None:
            return statement
        allowed = list(department_ids)
        document_ids = select(Document.id).where(
            Document.department_id.in_(allowed)
        )
        revision_ids = (
            select(DocumentRevision.id)
            .join(
                Document,
                Document.id == DocumentRevision.document_id,
            )
            .where(Document.department_id.in_(allowed))
        )
        file_ids = (
            select(DocumentFile.id)
            .join(
                Document,
                Document.id == DocumentFile.document_id,
            )
            .where(Document.department_id.in_(allowed))
        )
        return (
            statement.join(
                GlossaryTerm,
                GlossaryTerm.id == GlossaryException.glossary_term_id,
            )
            .join(
                GlossaryProfile,
                GlossaryProfile.id == GlossaryTerm.glossary_profile_id,
            )
            .where(
                or_(
                    GlossaryProfile.department_id.is_(None),
                    GlossaryProfile.department_id.in_(allowed),
                ),
                or_(
                    GlossaryException.scope_type
                    == GlossaryExceptionScopeType.GLOBAL,
                    and_(
                        GlossaryException.scope_type
                        == GlossaryExceptionScopeType.DEPARTMENT,
                        GlossaryException.department_id.in_(allowed),
                    ),
                    and_(
                        GlossaryException.scope_type
                        == GlossaryExceptionScopeType.DOCUMENT,
                        GlossaryException.document_id.in_(document_ids),
                    ),
                    and_(
                        GlossaryException.scope_type
                        == GlossaryExceptionScopeType.DOCUMENT_REVISION,
                        GlossaryException.document_revision_id.in_(
                            revision_ids
                        ),
                    ),
                    and_(
                        GlossaryException.scope_type
                        == GlossaryExceptionScopeType.DOCUMENT_FILE,
                        GlossaryException.document_file_id.in_(file_ids),
                    ),
                    GlossaryException.scope_type
                    == GlossaryExceptionScopeType.SECTION,
                ),
            )
        )
