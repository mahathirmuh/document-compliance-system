"""Database-only operations for retained similarity runs."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, raiseload

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.similarity_enums import SimilarityRunStatus
from app.models.similarity_run import SimilarityRun


class SimilarityRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_statement():
        return select(SimilarityRun).options(
            joinedload(SimilarityRun.document),
            joinedload(SimilarityRun.revision),
            joinedload(SimilarityRun.document_file),
            joinedload(SimilarityRun.requester),
            raiseload(SimilarityRun.results),
            raiseload(SimilarityRun.section_summaries),
        )

    async def add(self, run: SimilarityRun) -> SimilarityRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        for_update: bool = False,
    ) -> SimilarityRun | None:
        statement = self.base_statement().where(SimilarityRun.id == run_id)
        if department_ids is not None:
            statement = statement.join(
                Document, Document.id == SimilarityRun.document_id
            ).where(Document.department_id.in_(list(department_ids)))
        if for_update:
            statement = statement.with_for_update(of=SimilarityRun)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_job_id(
        self, job_id: UUID
    ) -> SimilarityRun | None:
        return (
            await self.session.execute(
                self.base_statement().where(
                    SimilarityRun.similarity_job_id == job_id
                )
            )
        ).scalar_one_or_none()

    async def find_equivalent(
        self,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID,
        source_content_hash: str,
        provider: str,
        model_name: str,
    ) -> SimilarityRun | None:
        statement = (
            self.base_statement()
            .where(
                SimilarityRun.document_file_id == document_file_id,
                SimilarityRun.compliance_run_id == compliance_run_id,
                SimilarityRun.status.in_(
                    {
                        SimilarityRunStatus.COMPLETED,
                        SimilarityRunStatus.PARTIALLY_COMPLETED,
                    }
                ),
                SimilarityRun.source_content_hash
                == source_content_hash.strip().lower(),
                SimilarityRun.provider == provider,
                SimilarityRun.model_name == model_name,
            )
            .order_by(
                desc(SimilarityRun.created_at),
                desc(SimilarityRun.id),
            )
            .limit(1)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_latest_for_file(
        self,
        document_file_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
    ) -> SimilarityRun | None:
        statement = (
            self.base_statement()
            .where(SimilarityRun.document_file_id == document_file_id)
            .order_by(
                desc(SimilarityRun.created_at),
                desc(SimilarityRun.id),
            )
            .limit(1)
        )
        if department_ids is not None:
            statement = statement.join(
                Document, Document.id == SimilarityRun.document_id
            ).where(Document.department_id.in_(list(department_ids)))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_for_file(
        self,
        document_file_id: UUID,
        *,
        department_ids: Sequence[UUID] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SimilarityRun], int]:
        statement = self.base_statement().where(
            SimilarityRun.document_file_id == document_file_id
        )
        if department_ids is not None:
            statement = statement.join(
                Document, Document.id == SimilarityRun.document_id
            ).where(Document.department_id.in_(list(department_ids)))
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
        rows = await self.session.scalars(
            statement.order_by(
                desc(SimilarityRun.created_at),
                desc(SimilarityRun.id),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.unique().all()), total

    async def set_latest_for_file(
        self,
        *,
        document_file_id: UUID,
        similarity_run_id: UUID,
    ) -> bool:
        """Update the Phase 9 pointer once the shared model is integrated."""

        latest_column = getattr(
            DocumentFile, "latest_similarity_run_id", None
        )
        if latest_column is None:
            return False
        await self.session.execute(
            update(DocumentFile)
            .where(DocumentFile.id == document_file_id)
            .values(latest_similarity_run_id=similarity_run_id)
        )
        await self.session.flush()
        return True
