"""Persistence operations for immutable language detection runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document_file import DocumentFile
from app.models.language_detection_job import LanguageDetectionJob
from app.models.language_detection_run import LanguageDetectionRun


class LanguageDetectionRunRepository:
    """Database-only run/history/latest operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options() -> tuple[object, ...]:
        return (
            joinedload(LanguageDetectionRun.job).joinedload(
                LanguageDetectionJob.requester
            ),
            joinedload(LanguageDetectionRun.document),
            joinedload(LanguageDetectionRun.revision),
            joinedload(LanguageDetectionRun.document_file),
            joinedload(LanguageDetectionRun.requester),
        )

    async def create(
        self,
        run: LanguageDetectionRun,
    ) -> LanguageDetectionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self,
        run_id: UUID,
        *,
        for_update: bool = False,
    ) -> LanguageDetectionRun | None:
        statement = (
            select(LanguageDetectionRun)
            .where(LanguageDetectionRun.id == run_id)
            .options(*self._options())
        )
        if for_update:
            statement = statement.with_for_update(
                of=LanguageDetectionRun
            )
        return await self.session.scalar(statement)

    async def get_latest_by_file(
        self,
        document_file_id: UUID,
    ) -> LanguageDetectionRun | None:
        latest_column = DocumentFile.latest_language_detection_run_id
        statement = (
            select(LanguageDetectionRun)
            .join(
                DocumentFile,
                latest_column == LanguageDetectionRun.id,
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
    ) -> list[LanguageDetectionRun]:
        statement = (
            select(LanguageDetectionRun)
            .where(
                LanguageDetectionRun.document_file_id == document_file_id
            )
            .options(*self._options())
            .order_by(
                LanguageDetectionRun.created_at.desc(),
                LanguageDetectionRun.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(
            (await self.session.scalars(statement)).unique().all()
        )

    async def count_by_file(self, document_file_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(LanguageDetectionRun.id)).where(
                    LanguageDetectionRun.document_file_id
                    == document_file_id
                )
            )
            or 0
        )

    async def find_by_source_hash(
        self,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID,
        ocr_run_id: UUID | None,
        source_content_hash: str,
    ) -> LanguageDetectionRun | None:
        statement = select(LanguageDetectionRun).where(
            LanguageDetectionRun.document_file_id == document_file_id,
            LanguageDetectionRun.extraction_run_id == extraction_run_id,
            LanguageDetectionRun.source_content_hash
            == source_content_hash.strip().lower(),
        )
        if ocr_run_id is None:
            statement = statement.where(
                LanguageDetectionRun.ocr_run_id.is_(None)
            )
        else:
            statement = statement.where(
                LanguageDetectionRun.ocr_run_id == ocr_run_id
            )
        statement = (
            statement.options(*self._options())
            .order_by(
                LanguageDetectionRun.created_at.desc(),
                LanguageDetectionRun.id.desc(),
            )
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def set_latest_by_ids(
        self,
        *,
        document_file_id: UUID,
        language_detection_run_id: UUID,
    ) -> None:
        latest_column = DocumentFile.latest_language_detection_run_id
        await self.session.execute(
            update(DocumentFile)
            .where(DocumentFile.id == document_file_id)
            .values({latest_column: language_detection_run_id})
        )
        await self.session.flush()
