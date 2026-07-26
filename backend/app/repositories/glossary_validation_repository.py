"""Persistence operations for glossary validation lifecycles."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.glossary_enums import (
    ACTIVE_GLOSSARY_VALIDATION_STATUSES,
    GlossaryValidationStatus,
)
from app.models.glossary_validation_run import GlossaryValidationRun


class GlossaryValidationRepository:
    """Bounded job/history access with mandatory optional department scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(GlossaryValidationRun)

    async def add(
        self,
        run: GlossaryValidationRun,
    ) -> GlossaryValidationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> GlossaryValidationRun | None:
        statement = self.base_statement().where(
            GlossaryValidationRun.id == run_id
        )
        statement = self._scope_to_departments(statement, department_ids)
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryValidationRun
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_active_for_file(
        self,
        document_file_id: UUID,
        *,
        source_content_hash: str | None = None,
        for_update: bool = False,
    ) -> GlossaryValidationRun | None:
        statement = self.base_statement().where(
            GlossaryValidationRun.document_file_id == document_file_id,
            GlossaryValidationRun.status.in_(
                ACTIVE_GLOSSARY_VALIDATION_STATUSES
            ),
        )
        if source_content_hash is not None:
            statement = statement.where(
                GlossaryValidationRun.source_content_hash
                == source_content_hash.strip().lower()
            )
        if for_update:
            statement = statement.with_for_update(
                of=GlossaryValidationRun
            ).execution_options(populate_existing=True)
        return (
            await self.session.execute(
                statement.order_by(
                    desc(GlossaryValidationRun.requested_at)
                ).limit(1)
            )
        ).scalar_one_or_none()

    async def get_latest_completed_for_file(
        self,
        document_file_id: UUID,
        *,
        source_content_hash: str | None = None,
        profile_ids: Sequence[UUID] | None = None,
    ) -> GlossaryValidationRun | None:
        statement = self.base_statement().where(
            GlossaryValidationRun.document_file_id == document_file_id,
            GlossaryValidationRun.status.in_(
                {
                    GlossaryValidationStatus.COMPLETED,
                    GlossaryValidationStatus.PARTIALLY_COMPLETED,
                }
            ),
        )
        if source_content_hash is not None:
            statement = statement.where(
                GlossaryValidationRun.source_content_hash
                == source_content_hash.strip().lower()
            )
        result = await self.session.scalars(
            statement.order_by(
                desc(GlossaryValidationRun.completed_at),
                desc(GlossaryValidationRun.created_at),
            )
        )
        expected = (
            {str(item) for item in profile_ids}
            if profile_ids is not None
            else None
        )
        for item in result.unique().all():
            actual = set(item.glossary_profile_ids_json)
            if expected is None or actual == expected:
                return item
        return None

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        document_id: UUID | None = None,
        document_file_id: UUID | None = None,
        status: GlossaryValidationStatus | None = None,
        requested_by: UUID | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_order: str = "desc",
    ) -> tuple[list[GlossaryValidationRun], int]:
        statement = self.base_statement()
        if department_ids is not None or search:
            statement = statement.join(
                Document,
                Document.id == GlossaryValidationRun.document_id,
            )
        if department_ids is not None:
            statement = statement.where(
                Document.department_id.in_(list(department_ids))
            )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    GlossaryValidationRun.current_stage.ilike(pattern),
                )
            )
        if document_id is not None:
            statement = statement.where(
                GlossaryValidationRun.document_id == document_id
            )
        if document_file_id is not None:
            statement = statement.where(
                GlossaryValidationRun.document_file_id == document_file_id
            )
        if status is not None:
            statement = statement.where(
                GlossaryValidationRun.status == status
            )
        if requested_by is not None:
            statement = statement.where(
                GlossaryValidationRun.requested_by == requested_by
            )
        if requested_from is not None:
            statement = statement.where(
                GlossaryValidationRun.requested_at >= requested_from
            )
        if requested_to is not None:
            statement = statement.where(
                GlossaryValidationRun.requested_at <= requested_to
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
            asc(GlossaryValidationRun.requested_at)
            if sort_order == "asc"
            else desc(GlossaryValidationRun.requested_at)
        )
        result = await self.session.scalars(
            statement.order_by(order, GlossaryValidationRun.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    @staticmethod
    def _scope_to_departments(statement, department_ids):
        if department_ids is None:
            return statement
        return statement.join(
            Document,
            Document.id == GlossaryValidationRun.document_id,
        ).where(Document.department_id.in_(list(department_ids)))
