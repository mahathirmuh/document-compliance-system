"""Persistence operations for immutable OCR runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document_file import DocumentFile
from app.models.ocr_job import OCRJob
from app.models.ocr_run import OCRRun


class OCRRunRepository:
    """Database-only OCR run reads, history, and latest marker updates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(OCRRun.ocr_job).joinedload(OCRJob.requester),
            joinedload(OCRRun.document),
            joinedload(OCRRun.revision),
            joinedload(OCRRun.document_file),
        )

    async def create(self, run: OCRRun) -> OCRRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        for_update: bool = False,
    ) -> OCRRun | None:
        statement = select(OCRRun).where(OCRRun.id == run_id).options(*self._options())
        if for_update:
            statement = statement.with_for_update(of=OCRRun)
        return await self.session.scalar(statement)

    async def get_by_job_id(self, ocr_job_id: UUID) -> OCRRun | None:
        return await self.session.scalar(
            select(OCRRun)
            .where(OCRRun.ocr_job_id == ocr_job_id)
            .options(*self._options())
        )

    async def get_latest_by_file(
        self,
        document_file_id: UUID,
    ) -> OCRRun | None:
        latest_column = getattr(DocumentFile, "latest_ocr_run_id", None)
        if latest_column is None:
            statement = (
                select(OCRRun)
                .where(OCRRun.document_file_id == document_file_id)
                .options(*self._options())
                .order_by(OCRRun.created_at.desc(), OCRRun.id.desc())
                .limit(1)
            )
        else:
            statement = (
                select(OCRRun)
                .join(DocumentFile, latest_column == OCRRun.id)
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
    ) -> list[OCRRun]:
        rows = await self.session.scalars(
            select(OCRRun)
            .where(OCRRun.document_file_id == document_file_id)
            .options(*self._options())
            .order_by(OCRRun.created_at.desc(), OCRRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.unique().all())

    async def count_by_file(self, document_file_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(OCRRun.id)).where(
                    OCRRun.document_file_id == document_file_id
                )
            )
            or 0
        )

    async def set_latest_by_ids(
        self,
        *,
        document_file_id: UUID,
        ocr_run_id: UUID,
    ) -> None:
        latest_column = getattr(DocumentFile, "latest_ocr_run_id", None)
        if latest_column is None:
            raise RuntimeError("DocumentFile.latest_ocr_run_id is not integrated.")
        document_file = await self.session.get(
            DocumentFile,
            document_file_id,
        )
        if document_file is None:
            raise ValueError("Latest OCR document file does not exist.")
        document_file.latest_ocr_run_id = ocr_run_id
        await self.session.flush()
