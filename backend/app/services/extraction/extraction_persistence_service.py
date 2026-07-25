"""Atomic persistence of normalized document extraction results."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.document_file import DocumentFile
from app.models.extracted_block import ExtractedBlock
from app.models.extracted_block import (
    ExtractedBlockType as PersistedBlockType,
)
from app.models.extracted_container import ExtractedContainer
from app.models.extracted_container import (
    ExtractedContainerType as PersistedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extracted_table_cell import ExtractedTableCell
from app.models.extraction_job import (
    ExtractionJob,
    ExtractionJobStatus,
)
from app.models.extraction_run import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractorType,
)
from app.repositories.extracted_block_repository import (
    ExtractedBlockRepository,
)
from app.repositories.extracted_container_repository import (
    ExtractedContainerRepository,
)
from app.repositories.extracted_table_repository import (
    ExtractedTableRepository,
)
from app.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from app.repositories.extraction_run_repository import (
    ExtractionRunRepository,
)
from app.schemas.extraction import (
    ExtractedContainerData,
    ExtractedDocumentData,
    ExtractedTableData,
)
from app.services.extraction.extraction_summary_service import (
    ExtractionSummary,
    ExtractionSummaryService,
)
from app.services.extraction.text_normalizer import calculate_content_hash

ItemT = TypeVar("ItemT")


def _chunks(
    items: Sequence[ItemT],
    size: int,
) -> Iterator[Sequence[ItemT]]:
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


class ExtractionPersistenceService:
    """Persist one complete normalized result inside one savepoint.

    The caller owns the outer transaction and must commit after this method
    returns. Repository methods deliberately only flush.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.job_repository = ExtractionJobRepository(session)
        self.run_repository = ExtractionRunRepository(session)
        self.container_repository = ExtractedContainerRepository(session)
        self.block_repository = ExtractedBlockRepository(session)
        self.table_repository = ExtractedTableRepository(session)

    async def persist_result(
        self,
        *,
        job: ExtractionJob,
        document_file: DocumentFile,
        result: ExtractedDocumentData,
        completed_at: datetime | None = None,
    ) -> ExtractionRun:
        """Atomically retain a run, all content, latest pointer, and job."""
        self._validate_source(job, document_file)
        finished_at = completed_at or datetime.now(UTC)
        summary = ExtractionSummaryService.calculate(result)
        content_hash = calculate_content_hash(result.containers)
        previous_run = await self.run_repository.get_latest_by_file(
            document_file.id
        )
        run_metadata = self._run_metadata(
            job=job,
            result=result,
            previous_run=previous_run,
            content_hash=content_hash,
        )

        async with self.session.begin_nested():
            run = await self.run_repository.create(
                ExtractionRun(
                    extraction_job_id=job.id,
                    document_id=job.document_id,
                    document_revision_id=job.document_revision_id,
                    document_file_id=job.document_file_id,
                    extractor_type=ExtractorType(result.extractor_type),
                    extractor_version=result.extractor_version,
                    status=ExtractionRunStatus(result.status.value),
                    source_sha256_hash=document_file.sha256_hash,
                    source_file_size=document_file.file_size,
                    content_hash=content_hash,
                    total_pages=summary.total_pages,
                    total_sheets=summary.total_sheets,
                    total_blocks=summary.total_blocks,
                    total_paragraphs=summary.total_paragraphs,
                    total_tables=summary.total_tables,
                    total_cells=summary.total_cells,
                    total_characters=summary.total_characters,
                    total_words=summary.total_words,
                    has_selectable_text=result.has_selectable_text,
                    requires_ocr=result.requires_ocr,
                    warnings_json=list(result.warnings),
                    metadata_json=run_metadata,
                    started_at=job.started_at or job.requested_at,
                    completed_at=finished_at,
                )
            )
            container_pairs = await self._persist_containers(
                run,
                result.containers,
            )
            await self._persist_blocks(run, container_pairs)
            await self._persist_tables(run, container_pairs)
            await self.run_repository.set_latest(document_file, run)
            await self.job_repository.mark_completed(
                job,
                status=ExtractionJobStatus(result.status.value),
                completed_at=finished_at,
                result_summary=self._job_summary(
                    run,
                    result,
                    summary,
                ),
            )
        return run

    async def persist(
        self,
        *,
        job: ExtractionJob,
        document_file: DocumentFile,
        result: ExtractedDocumentData,
        completed_at: datetime | None = None,
    ) -> ExtractionRun:
        """Compatibility alias for orchestration code."""
        return await self.persist_result(
            job=job,
            document_file=document_file,
            result=result,
            completed_at=completed_at,
        )

    async def _persist_containers(
        self,
        run: ExtractionRun,
        data: Sequence[ExtractedContainerData],
    ) -> list[tuple[ExtractedContainerData, ExtractedContainer]]:
        models = [
            ExtractedContainer(
                extraction_run_id=run.id,
                container_type=PersistedContainerType(
                    container.container_type.value
                ),
                container_index=container.container_index,
                name=container.name,
                title=container.title,
                raw_text=container.raw_text,
                normalised_text=container.normalised_text,
                character_count=container.character_count,
                word_count=container.word_count,
                metadata_json=dict(container.metadata),
            )
            for container in data
        ]
        for chunk in _chunks(models, self.settings.extraction_db_batch_size):
            await self.container_repository.bulk_create(chunk)
            for model in chunk:
                self.session.expunge(model)
        return list(zip(data, models, strict=True))

    async def _persist_blocks(
        self,
        run: ExtractionRun,
        container_pairs: Sequence[
            tuple[ExtractedContainerData, ExtractedContainer]
        ],
    ) -> None:
        for container_data, container in container_pairs:
            referenced_parent_orders = {
                block.parent_block_order
                for block in container_data.blocks
                if block.parent_block_order is not None
            }
            parent_ids: dict[int, UUID] = {}
            previous_order = 0
            batch: list[ExtractedBlock] = []
            for block_data in container_data.blocks:
                if block_data.block_order <= previous_order:
                    raise ValueError(
                        "Block order must be unique and increasing within "
                        "a container."
                    )
                previous_order = block_data.block_order
                parent_id: UUID | None = None
                if block_data.parent_block_order is not None:
                    parent_id = parent_ids.get(
                        block_data.parent_block_order
                    )
                    if parent_id is None:
                        raise ValueError(
                            "Parent block order must exist earlier in the "
                            "same container."
                        )
                block_id = uuid4()
                block = ExtractedBlock(
                    id=block_id,
                    extraction_run_id=run.id,
                    container_id=container.id,
                    parent_block_id=parent_id,
                    block_type=PersistedBlockType(
                        block_data.block_type.value
                    ),
                    block_order=block_data.block_order,
                    source_reference=block_data.source_reference,
                    text=block_data.text,
                    normalised_text=block_data.normalised_text,
                    style_name=block_data.style_name,
                    heading_level=block_data.heading_level,
                    location_json=dict(block_data.location),
                    metadata_json=dict(block_data.metadata),
                    character_count=block_data.character_count,
                    word_count=block_data.word_count,
                )
                if block_data.block_order in referenced_parent_orders:
                    parent_ids[block_data.block_order] = block_id
                batch.append(block)
                if len(batch) >= self.settings.extraction_db_batch_size:
                    await self._flush_block_batch(batch)
            if batch:
                await self._flush_block_batch(batch)

    async def _flush_block_batch(
        self,
        batch: list[ExtractedBlock],
    ) -> None:
        await self.block_repository.bulk_create(batch)
        for block in batch:
            self.session.expunge(block)
        batch.clear()

    async def _persist_tables(
        self,
        run: ExtractionRun,
        container_pairs: Sequence[
            tuple[ExtractedContainerData, ExtractedContainer]
        ],
    ) -> None:
        table_pairs: list[tuple[ExtractedTableData, ExtractedTable]] = []
        table_models: list[ExtractedTable] = []
        for container_data, container in container_pairs:
            for table_data in container_data.tables:
                table = ExtractedTable(
                    extraction_run_id=run.id,
                    container_id=container.id,
                    source_reference=table_data.source_reference,
                    table_index=table_data.table_index,
                    row_count=table_data.row_count,
                    column_count=table_data.column_count,
                    raw_text=table_data.raw_text,
                    metadata_json=dict(table_data.metadata),
                )
                table_models.append(table)
                table_pairs.append((table_data, table))
        for chunk in _chunks(
            table_models,
            self.settings.extraction_db_batch_size,
        ):
            await self.table_repository.bulk_create(chunk)
            for table in chunk:
                self.session.expunge(table)

        cell_batch: list[ExtractedTableCell] = []
        for table_data, table in table_pairs:
            for cell in table_data.cells:
                cell_batch.append(
                    ExtractedTableCell(
                        extracted_table_id=table.id,
                        row_index=cell.row_index,
                        column_index=cell.column_index,
                        row_span=cell.row_span,
                        column_span=cell.column_span,
                        coordinate=cell.coordinate,
                        text=cell.text,
                        normalised_text=cell.normalised_text,
                        metadata_json=dict(cell.metadata),
                    )
                )
                if (
                    len(cell_batch)
                    >= self.settings.extraction_db_batch_size
                ):
                    await self._flush_cell_batch(cell_batch)
        if cell_batch:
            await self._flush_cell_batch(cell_batch)

    async def _flush_cell_batch(
        self,
        batch: list[ExtractedTableCell],
    ) -> None:
        await self.table_repository.bulk_create_cells(batch)
        for cell in batch:
            self.session.expunge(cell)
        batch.clear()

    @staticmethod
    def _validate_source(
        job: ExtractionJob,
        document_file: DocumentFile,
    ) -> None:
        if job.document_file_id != document_file.id:
            raise ValueError(
                "Extraction job and source document file do not match."
            )
        if job.document_id != document_file.document_id:
            raise ValueError(
                "Extraction job and source document do not match."
            )
        if (
            job.document_revision_id
            != document_file.document_revision_id
        ):
            raise ValueError(
                "Extraction job and source revision do not match."
            )

    @staticmethod
    def _run_metadata(
        *,
        job: ExtractionJob,
        result: ExtractedDocumentData,
        previous_run: ExtractionRun | None,
        content_hash: str,
    ) -> dict[str, object]:
        metadata: dict[str, object] = dict(result.metadata)
        metadata["contentUnchanged"] = bool(
            previous_run is not None
            and previous_run.content_hash == content_hash
        )
        reason = (job.result_summary_json or {}).get(
            "reExtractionReason"
        )
        if isinstance(reason, str) and reason.strip():
            metadata["reExtractionReason"] = reason.strip()
        return metadata

    @staticmethod
    def _job_summary(
        run: ExtractionRun,
        result: ExtractedDocumentData,
        summary: ExtractionSummary,
    ) -> dict[str, object]:
        return {
            "runId": str(run.id),
            "status": result.status.value,
            "extractorType": result.extractor_type,
            **summary.as_dict(),
            "requiresOcr": result.requires_ocr,
            "warnings": list(result.warnings),
        }
