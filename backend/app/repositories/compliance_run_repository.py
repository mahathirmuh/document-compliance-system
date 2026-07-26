"""Persistence operations for retained compliance runs."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, raiseload, selectinload

from app.models.compliance_run import ComplianceRun
from app.models.document import Document
from app.models.document_file import DocumentFile


class ComplianceRunRepository:
    """Database-only immutable run operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(
        self,
        *,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ):
        """Build a run query without implicitly materializing large children."""

        statement = select(ComplianceRun).options(
            joinedload(ComplianceRun.document),
            joinedload(ComplianceRun.revision),
            joinedload(ComplianceRun.document_file),
            joinedload(ComplianceRun.validation_rule),
            joinedload(ComplianceRun.requester),
        )
        statement = statement.options(
            (
                selectinload(ComplianceRun.detected_sections)
                if include_detected_sections
                else raiseload(ComplianceRun.detected_sections)
            ),
            (
                selectinload(ComplianceRun.translation_groups)
                if include_translation_groups
                else raiseload(ComplianceRun.translation_groups)
            ),
        )
        return statement

    async def add(self, run: ComplianceRun) -> ComplianceRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ) -> ComplianceRun | None:
        statement = self.base_statement(
            include_detected_sections=include_detected_sections,
            include_translation_groups=include_translation_groups,
        ).where(ComplianceRun.id == run_id)
        if department_ids is not None:
            statement = statement.join(
                Document,
                Document.id == ComplianceRun.document_id,
            ).where(Document.department_id.in_(list(department_ids)))
        if for_update:
            statement = statement.with_for_update(of=ComplianceRun)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_job_id(
        self,
        compliance_job_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ) -> ComplianceRun | None:
        statement = self.base_statement(
            include_detected_sections=include_detected_sections,
            include_translation_groups=include_translation_groups,
        ).where(ComplianceRun.compliance_job_id == compliance_job_id)
        if department_ids is not None:
            statement = statement.join(
                Document,
                Document.id == ComplianceRun.document_id,
            ).where(Document.department_id.in_(list(department_ids)))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_latest_for_file(
        self,
        document_file_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ) -> ComplianceRun | None:
        statement = (
            self.base_statement(
                include_detected_sections=include_detected_sections,
                include_translation_groups=include_translation_groups,
            )
            .where(ComplianceRun.document_file_id == document_file_id)
            .order_by(
                desc(ComplianceRun.created_at),
                desc(ComplianceRun.id),
            )
            .limit(1)
        )
        if department_ids is not None:
            statement = statement.join(
                Document,
                Document.id == ComplianceRun.document_id,
            ).where(Document.department_id.in_(list(department_ids)))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def find_equivalent(
        self,
        *,
        document_file_id: UUID,
        source_content_hash: str,
        validation_rule_id: UUID,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ) -> ComplianceRun | None:
        statement = (
            self.base_statement(
                include_detected_sections=include_detected_sections,
                include_translation_groups=include_translation_groups,
            )
            .where(
                ComplianceRun.document_file_id == document_file_id,
                ComplianceRun.source_content_hash
                == source_content_hash.strip().lower(),
                ComplianceRun.validation_rule_id == validation_rule_id,
            )
            .order_by(desc(ComplianceRun.created_at))
            .limit(1)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def set_latest_for_file(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID,
    ) -> None:
        await self.session.execute(
            update(DocumentFile)
            .where(DocumentFile.id == document_file_id)
            .values(latest_compliance_run_id=compliance_run_id)
        )
        await self.session.flush()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        document_id: UUID | None = None,
        document_file_id: UUID | None = None,
        validation_rule_id: UUID | None = None,
        compliance_status: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        include_detected_sections: bool = False,
        include_translation_groups: bool = False,
    ) -> tuple[list[ComplianceRun], int]:
        statement = self.base_statement(
            include_detected_sections=include_detected_sections,
            include_translation_groups=include_translation_groups,
        )
        if department_ids is not None or search:
            statement = statement.join(
                Document,
                Document.id == ComplianceRun.document_id,
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
                )
            )
        if document_id is not None:
            statement = statement.where(
                ComplianceRun.document_id == document_id
            )
        if document_file_id is not None:
            statement = statement.where(
                ComplianceRun.document_file_id == document_file_id
            )
        if validation_rule_id is not None:
            statement = statement.where(
                ComplianceRun.validation_rule_id == validation_rule_id
            )
        if compliance_status is not None:
            statement = statement.where(
                ComplianceRun.compliance_status == compliance_status
            )
        if created_from is not None:
            statement = statement.where(
                ComplianceRun.created_at >= created_from
            )
        if created_to is not None:
            statement = statement.where(
                ComplianceRun.created_at <= created_to
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
        result = await self.session.scalars(
            statement.order_by(
                desc(ComplianceRun.created_at),
                desc(ComplianceRun.id),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
