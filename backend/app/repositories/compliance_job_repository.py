"""Persistence operations for compliance validation jobs."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.compliance_enums import (
    ACTIVE_COMPLIANCE_JOB_STATUSES,
    ComplianceJobStatus,
    ComplianceStatus,
)
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.document import Document


class ComplianceJobRepository:
    """Database-only compliance-job operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(self):
        return select(ComplianceJob).options(
            joinedload(ComplianceJob.document),
            joinedload(ComplianceJob.revision),
            joinedload(ComplianceJob.document_file),
            joinedload(ComplianceJob.validation_rule),
            joinedload(ComplianceJob.requester),
            joinedload(ComplianceJob.compliance_run),
        )

    async def add(self, job: ComplianceJob) -> ComplianceJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> ComplianceJob | None:
        statement = self.base_statement().where(ComplianceJob.id == job_id)
        if department_ids is not None:
            statement = statement.join(
                Document,
                Document.id == ComplianceJob.document_id,
            ).where(Document.department_id.in_(list(department_ids)))
        if for_update:
            statement = statement.with_for_update(
                of=ComplianceJob
            ).execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_active(
        self,
        document_file_id: UUID,
        *,
        source_content_hash: str | None = None,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> ComplianceJob | None:
        statement = self.base_statement().where(
            ComplianceJob.document_file_id == document_file_id,
            ComplianceJob.status.in_(ACTIVE_COMPLIANCE_JOB_STATUSES),
        )
        if department_ids is not None:
            statement = statement.join(
                Document,
                Document.id == ComplianceJob.document_id,
            ).where(Document.department_id.in_(list(department_ids)))
        if source_content_hash is not None:
            statement = statement.where(
                ComplianceJob.source_content_hash
                == source_content_hash.strip().lower()
            )
        if for_update:
            statement = statement.with_for_update(
                of=ComplianceJob
            ).execution_options(populate_existing=True)
        return (
            await self.session.execute(
                statement.order_by(desc(ComplianceJob.requested_at)).limit(1)
            )
        ).scalar_one_or_none()

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        document_file_id: UUID | None = None,
        validation_rule_id: UUID | None = None,
        compliance_status: ComplianceStatus | None = None,
        requested_by: UUID | None = None,
        statuses: Sequence[ComplianceJobStatus] | None = None,
        requested_from: datetime | None = None,
        requested_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "requestedAt",
        sort_order: str = "desc",
    ) -> tuple[list[ComplianceJob], int]:
        statement = self.base_statement()
        if department_ids is not None or search:
            statement = statement.join(
                Document,
                Document.id == ComplianceJob.document_id,
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
                    ComplianceJob.current_stage.ilike(pattern),
                )
            )
        if document_id is not None:
            statement = statement.where(
                ComplianceJob.document_id == document_id
            )
        if revision_id is not None:
            statement = statement.where(
                ComplianceJob.document_revision_id == revision_id
            )
        if document_file_id is not None:
            statement = statement.where(
                ComplianceJob.document_file_id == document_file_id
            )
        if validation_rule_id is not None:
            statement = statement.where(
                ComplianceJob.validation_rule_id == validation_rule_id
            )
        if compliance_status is not None:
            statement = statement.join(
                ComplianceRun,
                ComplianceRun.compliance_job_id == ComplianceJob.id,
            ).where(ComplianceRun.compliance_status == compliance_status)
        if requested_by is not None:
            statement = statement.where(
                ComplianceJob.requested_by == requested_by
            )
        if statuses:
            statement = statement.where(
                ComplianceJob.status.in_(list(statuses))
            )
        if requested_from is not None:
            statement = statement.where(
                ComplianceJob.requested_at >= requested_from
            )
        if requested_to is not None:
            statement = statement.where(
                ComplianceJob.requested_at <= requested_to
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
        sort_columns = {
            "requestedAt": ComplianceJob.requested_at,
            "completedAt": ComplianceJob.completed_at,
            "status": ComplianceJob.status,
            "progress": ComplianceJob.progress,
        }
        sort_column = sort_columns.get(sort_by, ComplianceJob.requested_at)
        ordering = (
            asc(sort_column)
            if sort_order == "asc"
            else desc(sort_column)
        )
        result = await self.session.scalars(
            statement.order_by(ordering, ComplianceJob.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
