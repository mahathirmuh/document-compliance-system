"""Focused Phase 6 model, migration, and repository tests."""

from __future__ import annotations

import runpy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.core.authorization import (
    AuditAction,
    Permission,
    UserRole,
    get_permissions,
)
from app.database.base import Base
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extracted_table_cell import ExtractedTableCell
from app.models.extraction_job import (
    ACTIVE_EXTRACTION_JOB_STATUSES,
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
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
    ExtractedBlockData,
    ExtractedContainerData,
    ExtractedDocumentData,
    ExtractedTableCellData,
    ExtractedTableData,
    ExtractionResultStatus,
)
from app.schemas.extraction import ExtractedBlockType as SchemaBlockType
from app.schemas.extraction import (
    ExtractedContainerType as SchemaContainerType,
)
from app.services.extraction.extraction_persistence_service import (
    ExtractionPersistenceService,
)


def _extracted_result(
    *,
    parent_block_order: int | None = 1,
) -> ExtractedDocumentData:
    return ExtractedDocumentData(
        extractor_type="PDF",
        extractor_version="1.0.0",
        status=ExtractionResultStatus.COMPLETED,
        metadata={"producer": "generated-test"},
        containers=[
            ExtractedContainerData(
                container_type=SchemaContainerType.PDF_PAGE,
                container_index=1,
                name="Page 1",
                raw_text="Document control\nPolicy",
                normalised_text="Document control\nPolicy",
                character_count=23,
                word_count=3,
                blocks=[
                    ExtractedBlockData(
                        block_type=SchemaBlockType.HEADING,
                        block_order=1,
                        source_reference="PDF:page=1:block=1",
                        text="Document control",
                        normalised_text="Document control",
                        heading_level=1,
                        location={"page": 1},
                        character_count=16,
                        word_count=2,
                    ),
                    ExtractedBlockData(
                        block_type=SchemaBlockType.TEXT,
                        block_order=2,
                        source_reference="PDF:page=1:block=2",
                        text="Policy",
                        normalised_text="Policy",
                        parent_block_order=parent_block_order,
                        location={"page": 1},
                        character_count=6,
                        word_count=1,
                    ),
                ],
                tables=[
                    ExtractedTableData(
                        source_reference="PDF:page=1:table=1",
                        table_index=1,
                        row_count=1,
                        column_count=1,
                        raw_text="Policy",
                        cells=[
                            ExtractedTableCellData(
                                row_index=1,
                                column_index=1,
                                coordinate="A1",
                                text="Policy",
                                normalised_text="Policy",
                            )
                        ],
                    )
                ],
            )
        ],
    )


def _document_graph() -> tuple[
    Document,
    DocumentRevision,
    DocumentFile,
]:
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number="006",
        base_document_code="MTI-HRM-POL-006",
        title="Phase 6 Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-HRM-POL-006_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="MTI-HRM-POL-006_Rev.000.pdf",
        sanitized_filename="MTI-HRM-POL-006_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=1234,
        sha256_hash="a" * 64,
        storage_key="documents/originals/phase6/source.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    return document, revision, document_file


def _job(
    document: Document,
    revision: DocumentRevision,
    document_file: DocumentFile,
    *,
    status: ExtractionJobStatus = ExtractionJobStatus.QUEUED,
) -> ExtractionJob:
    return ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=status,
        progress=0,
    )


def _run(
    job: ExtractionJob,
    document: Document,
    revision: DocumentRevision,
    document_file: DocumentFile,
    *,
    content_hash: str = "b" * 64,
) -> ExtractionRun:
    return ExtractionRun(
        extraction_job=job,
        document=document,
        revision=revision,
        document_file=document_file,
        extractor_type=ExtractorType.PDF,
        extractor_version="1.0.0",
        status=ExtractionRunStatus.COMPLETED,
        source_sha256_hash=document_file.sha256_hash,
        source_file_size=document_file.file_size,
        content_hash=content_hash,
        warnings_json=[],
        total_pages=1,
        total_blocks=1,
        total_characters=14,
        total_words=2,
    )


def test_phase6_metadata_contains_tables_constraints_and_relationships() -> None:
    expected_tables = {
        "extraction_jobs",
        "extraction_runs",
        "extracted_containers",
        "extracted_blocks",
        "extracted_tables",
        "extracted_table_cells",
    }
    assert expected_tables.issubset(Base.metadata.tables)

    document_files = Base.metadata.tables["document_files"]
    assert "latest_extraction_run_id" in document_files.c

    job_indexes = {
        index.name
        for index in Base.metadata.tables["extraction_jobs"].indexes
    }
    assert "uq_extraction_jobs_one_active_per_file" in job_indexes
    active_index = next(
        index
        for index in Base.metadata.tables["extraction_jobs"].indexes
        if index.name == "uq_extraction_jobs_one_active_per_file"
    )
    assert active_index.unique is True
    assert active_index.dialect_options["postgresql"]["where"] is not None
    assert active_index.dialect_options["sqlite"]["where"] is not None

    file_relationships = set(
        inspect(DocumentFile).relationships.keys()
    )
    assert {
        "extraction_jobs",
        "extraction_runs",
        "latest_extraction_run",
    }.issubset(file_relationships)


def test_phase6_migration_is_linear_and_declares_exact_contract() -> None:
    migration = runpy.run_path(
        str(
            Path(__file__).parents[2]
            / "alembic"
            / "versions"
            / "20260725_0005_phase6_document_content_extraction.py"
        )
    )

    assert migration["revision"] == "20260725_0005"
    assert migration["down_revision"] == "20260725_0004"
    assert len(migration["PHASE6_AUDIT_ACTIONS"]) == 11
    assert set(migration["ACTIVE_EXTRACTION_JOB_STATUSES"]) == {
        status.value for status in ACTIVE_EXTRACTION_JOB_STATUSES
    }
    assert tuple(migration["EXTRACTOR_TYPES"]) == ("PDF", "DOCX", "XLSX")


def test_phase6_permission_and_audit_enums_are_complete() -> None:
    extraction_permissions = {
        "documents:extract",
        "documents:reextract",
        "documents:view_extracted_content",
        "documents:export_extracted_content",
        "documents:view_extraction_history",
        "documents:cancel_extraction",
    }
    assert extraction_permissions == {
        permission.value
        for permission in Permission
        if permission.value in extraction_permissions
    }
    assert extraction_permissions.issubset(
        set(get_permissions(UserRole.SUPER_ADMIN))
    )
    assert extraction_permissions.issubset(
        set(get_permissions(UserRole.DOCUMENT_CONTROLLER))
    )
    assert "documents:extract" in get_permissions(
        UserRole.DEPARTMENT_USER
    )
    assert "documents:reextract" not in get_permissions(
        UserRole.DEPARTMENT_USER
    )
    required_audit_actions = {
        "QUEUE_DOCUMENT_EXTRACTION",
        "COMPLETE_DOCUMENT_EXTRACTION",
        "DOCUMENT_REQUIRES_OCR",
        "FAIL_DOCUMENT_EXTRACTION",
        "CANCEL_DOCUMENT_EXTRACTION",
        "REEXTRACT_DOCUMENT",
        "EXPORT_EXTRACTED_CONTENT",
    }
    assert required_audit_actions.issubset(
        {action.value for action in AuditAction}
    )


@pytest.mark.asyncio
async def test_partial_unique_index_prevents_two_active_jobs_per_file(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    first = _job(document, revision, document_file)
    async with session_factory() as session:
        session.add_all([document, revision, document_file, first])
        await session.commit()
        first_id = first.id

        second = _job(document, revision, document_file)
        session.add(second)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        first = await ExtractionJobRepository(session).get_by_id(
            first_id,
            for_update=True,
        )
        assert first is not None
        await ExtractionJobRepository(session).mark_completed(
            first,
            status=ExtractionJobStatus.COMPLETED,
            completed_at=datetime.now(UTC),
        )
        await session.commit()

        third = ExtractionJob(
            document_id=first.document_id,
            document_revision_id=first.document_revision_id,
            document_file_id=first.document_file_id,
            job_type=ExtractionJobType.INITIAL_EXTRACTION,
            status=ExtractionJobStatus.QUEUED,
            progress=0,
        )
        session.add(third)
        await session.commit()
        assert third.id is not None


@pytest.mark.asyncio
async def test_repositories_retain_history_and_update_latest_run(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    async with session_factory() as session:
        session.add_all([document, revision, document_file])
        await session.commit()

        job_repository = ExtractionJobRepository(session)
        run_repository = ExtractionRunRepository(session)
        first_job = await job_repository.create(
            _job(
                document,
                revision,
                document_file,
                status=ExtractionJobStatus.COMPLETED,
            )
        )
        first_run = await run_repository.create(
            _run(first_job, document, revision, document_file)
        )
        await run_repository.set_latest(document_file, first_run)
        await session.commit()

        second_job = await job_repository.create(
            ExtractionJob(
                document=document,
                revision=revision,
                document_file=document_file,
                job_type=ExtractionJobType.RE_EXTRACTION,
                status=ExtractionJobStatus.COMPLETED,
                progress=100,
            )
        )
        second_run = await run_repository.create(
            _run(
                second_job,
                document,
                revision,
                document_file,
                content_hash="c" * 64,
            )
        )
        await run_repository.set_latest(document_file, second_run)
        await session.commit()

        latest = await run_repository.get_latest_by_file(document_file.id)
        history = await run_repository.list_by_file(document_file.id)
        assert latest is not None
        assert latest.id == second_run.id
        assert {item.id for item in history} == {
            first_run.id,
            second_run.id,
        }


@pytest.mark.asyncio
async def test_content_repositories_bulk_create_page_search_and_cells(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    job = _job(
        document,
        revision,
        document_file,
        status=ExtractionJobStatus.COMPLETED,
    )
    run = _run(job, document, revision, document_file)

    async with session_factory() as session:
        session.add_all([document, revision, document_file, job, run])
        await session.flush()

        container_repository = ExtractedContainerRepository(session)
        block_repository = ExtractedBlockRepository(session)
        table_repository = ExtractedTableRepository(session)
        container = (
            await container_repository.bulk_create(
                [
                    ExtractedContainer(
                        extraction_run_id=run.id,
                        container_type=ExtractedContainerType.PDF_PAGE,
                        container_index=1,
                        name="Page 1",
                        raw_text="Document control",
                        normalised_text="Document control",
                        character_count=16,
                        word_count=2,
                    )
                ]
            )
        )[0]
        block = (
            await block_repository.bulk_create(
                [
                    ExtractedBlock(
                        extraction_run_id=run.id,
                        container_id=container.id,
                        block_type=ExtractedBlockType.TEXT,
                        block_order=1,
                        source_reference="PDF:page=1:block=1",
                        text="Document control",
                        normalised_text="Document control",
                        character_count=16,
                        word_count=2,
                    )
                ]
            )
        )[0]
        table = (
            await table_repository.bulk_create(
                [
                    ExtractedTable(
                        extraction_run_id=run.id,
                        container_id=container.id,
                        source_reference="PDF:page=1:table=1",
                        table_index=1,
                        row_count=1,
                        column_count=1,
                        raw_text="Policy",
                    )
                ]
            )
        )[0]
        await table_repository.bulk_create_cells(
            [
                ExtractedTableCell(
                    extracted_table_id=table.id,
                    row_index=0,
                    column_index=0,
                    coordinate="A1",
                    text="Policy",
                    normalised_text="Policy",
                )
            ]
        )
        await session.commit()

        blocks, block_total = await block_repository.list(
            run.id,
            search="document",
        )
        search_results, search_total = await block_repository.search(
            run.id,
            "Page 1",
        )
        tables, table_total = await table_repository.list(
            run.id,
            include_cells=True,
        )
        cells, cell_total = await table_repository.list_cells(table.id)

        assert block_total == 1
        assert blocks[0].id == block.id
        assert search_total == 1
        assert search_results[0].container.name == "Page 1"
        assert table_total == 1
        assert tables[0].cells[0].text == "Policy"
        assert cell_total == 1
        assert cells[0].coordinate == "A1"


@pytest.mark.asyncio
async def test_persistence_service_is_atomic_retains_old_run_and_reason(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    first_job = _job(document, revision, document_file)
    async with session_factory() as session:
        session.add_all(
            [document, revision, document_file, first_job]
        )
        await session.commit()

        service = ExtractionPersistenceService(session)
        first_run = await service.persist_result(
            job=first_job,
            document_file=document_file,
            result=_extracted_result(),
        )
        await session.commit()

        assert first_job.status == ExtractionJobStatus.COMPLETED
        assert document_file.latest_extraction_run_id == first_run.id
        assert first_run.total_blocks == 2
        assert first_run.total_tables == 1
        assert first_run.metadata_json == {
            "producer": "generated-test",
            "contentUnchanged": False,
        }

        second_job = ExtractionJob(
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.RE_EXTRACTION,
            status=ExtractionJobStatus.QUEUED,
            progress=0,
            result_summary_json={
                "reExtractionReason": "Extractor configuration updated."
            },
        )
        session.add(second_job)
        await session.flush()
        second_run = await service.persist(
            job=second_job,
            document_file=document_file,
            result=_extracted_result(),
        )
        await session.commit()

        history = await ExtractionRunRepository(session).list_by_file(
            document_file.id
        )
        assert len(history) == 2
        assert document_file.latest_extraction_run_id == second_run.id
        assert second_run.content_hash == first_run.content_hash
        assert second_run.metadata_json is not None
        assert second_run.metadata_json["contentUnchanged"] is True
        assert (
            second_run.metadata_json["reExtractionReason"]
            == "Extractor configuration updated."
        )
        assert second_job.result_summary_json is not None
        assert (
            second_job.result_summary_json["reExtractionReason"]
            == "Extractor configuration updated."
        )
        assert second_job.result_summary_json["runId"] == str(second_run.id)


@pytest.mark.asyncio
async def test_persistence_service_rolls_back_partial_content_on_error(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    job = _job(document, revision, document_file)
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()

        with pytest.raises(
            ValueError,
            match="Parent block order must exist",
        ):
            await ExtractionPersistenceService(session).persist_result(
                job=job,
                document_file=document_file,
                result=_extracted_result(parent_block_order=99),
            )

        history = await ExtractionRunRepository(session).list_by_file(
            document_file.id
        )
        assert history == []
        assert document_file.latest_extraction_run_id is None
        assert job.status == ExtractionJobStatus.QUEUED
