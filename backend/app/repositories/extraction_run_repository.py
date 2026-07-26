"""Persistence operations for immutable extraction runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document_file import DocumentFile
from app.models.extraction_job import ExtractionJob
from app.models.extraction_run import ExtractionRun


class ExtractionRunRepository:
    """Database-only extraction-run operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(ExtractionRun.extraction_job).joinedload(
                ExtractionJob.requester
            ),
            joinedload(ExtractionRun.document),
            joinedload(ExtractionRun.revision),
            joinedload(ExtractionRun.document_file),
        )

    async def create(self, run: ExtractionRun) -> ExtractionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExtractionRun | None:
        statement = (
            select(ExtractionRun)
            .where(ExtractionRun.id == run_id)
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(of=ExtractionRun)
        return await self.session.scalar(statement)

    async def get_latest_by_file(
        self,
        document_file_id: UUID,
    ) -> ExtractionRun | None:
        statement = (
            select(ExtractionRun)
            .join(
                DocumentFile,
                DocumentFile.latest_extraction_run_id == ExtractionRun.id,
            )
            .where(DocumentFile.id == document_file_id)
            .options(*self._options())
        )
        return await self.session.scalar(statement)

    async def list_by_file(
        self,
        document_file_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ExtractionRun]:
        statement = (
            select(ExtractionRun)
            .where(ExtractionRun.document_file_id == document_file_id)
            .options(*self._options())
            .order_by(
                ExtractionRun.created_at.desc(),
                ExtractionRun.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).unique().all())

    async def find_by_source_hash(
        self,
        document_file_id: UUID,
        source_sha256_hash: str,
    ) -> ExtractionRun | None:
        statement = (
            select(ExtractionRun)
            .where(
                ExtractionRun.document_file_id == document_file_id,
                ExtractionRun.source_sha256_hash == source_sha256_hash.strip().lower(),
            )
            .options(*self._options())
            .order_by(
                ExtractionRun.created_at.desc(),
                ExtractionRun.id.desc(),
            )
        )
        return await self.session.scalar(statement)

    async def count_by_file(self, document_file_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(ExtractionRun.id)).where(
                    ExtractionRun.document_file_id == document_file_id
                )
            )
            or 0
        )

    async def set_latest(
        self,
        document_file: DocumentFile,
        extraction_run: ExtractionRun,
    ) -> DocumentFile:
        if extraction_run.document_file_id != document_file.id:
            raise ValueError("Latest extraction run must belong to the document file.")
        document_file.latest_extraction_run_id = extraction_run.id
        document_file.latest_ocr_run_id = None
        document_file.latest_language_detection_run_id = None
        await self.session.flush()
        return document_file

    async def set_latest_by_ids(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID,
    ) -> None:
        await self.session.execute(
            update(DocumentFile)
            .where(DocumentFile.id == document_file_id)
            .values(
                latest_extraction_run_id=extraction_run_id,
                latest_ocr_run_id=None,
                latest_language_detection_run_id=None,
            )
        )
        await self.session.flush()
