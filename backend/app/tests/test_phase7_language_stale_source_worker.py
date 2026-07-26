"""Regression tests for language-worker source snapshot consistency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.models.document_file import DocumentFile
from app.models.extraction_job import (
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractorType,
)
from app.models.language_detection_job import (
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.models.language_detection_run import LanguageDetectionRun
from app.models.ocr_job import (
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.repositories.language_detection_document_repository import (
    LanguageDetectionDocumentRepository,
    LanguageDetectionDocumentRow,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.language.fasttext_language_detector import (
    FastTextLanguageDetector,
)
from app.services.language.hybrid_language_detector import (
    HybridLanguageDetector,
)
from app.services.language.language_detection_document_service import (
    LanguageDetectionDocumentService,
)
from app.services.language.language_detection_job_service import (
    LanguageDetectionJobService,
)
from app.services.language.language_detection_service import (
    LanguageDetectionService,
)
from app.services.language.language_normalizer import (
    calculate_source_snapshot_hash,
)
from app.services.language.language_persistence_service import (
    LanguagePersistenceService,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.tests.test_phase7_language_persistence import (
    EnglishPredictor,
    _pipeline,
    _source_graph,
)


@dataclass(frozen=True, slots=True)
class SeededLanguageWorker:
    job_id: UUID
    document_id: UUID
    revision_id: UUID
    document_file_id: UUID
    extraction_run_id: UUID
    latest_language_run_id: UUID


async def _create_ocr_run(
    session: AsyncSession,
    *,
    document_id: UUID,
    revision_id: UUID,
    document_file_id: UUID,
    extraction_run_id: UUID,
    content_hash_character: str,
) -> OCRRun:
    now = datetime.now(UTC)
    ocr_job = OCRJob(
        document_id=document_id,
        document_revision_id=revision_id,
        document_file_id=document_file_id,
        extraction_run_id=extraction_run_id,
        job_type=OCRJobType.INITIAL_OCR,
        status=OCRJobStatus.COMPLETED,
        progress=100,
        current_stage="Completed",
        language_profile=OCRLanguageProfile.LATIN,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        requested_page_numbers_json=[1],
        processed_page_numbers_json=[1],
        failed_page_numbers_json=[],
        maximum_attempts=1,
        completed_at=now,
    )
    session.add(ocr_job)
    await session.flush()
    run = OCRRun(
        ocr_job_id=ocr_job.id,
        document_id=document_id,
        document_revision_id=revision_id,
        document_file_id=document_file_id,
        source_extraction_run_id=extraction_run_id,
        provider="paddleocr",
        provider_version="test",
        language_profile=OCRLanguageProfile.LATIN,
        status=OCRRunStatus.COMPLETED,
        source_sha256_hash="a" * 64,
        page_count_requested=1,
        page_count_processed=1,
        page_count_failed=0,
        total_blocks=1,
        total_characters=20,
        render_dpi=300,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        content_hash=content_hash_character * 64,
        warnings_json=[],
        metadata_json={},
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    await session.flush()
    return run


async def _seed_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    with_ocr: bool,
) -> SeededLanguageWorker:
    (
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
        block,
    ) = _source_graph()
    config = LanguageRuntimeConfig(database_batch_size=1)
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                container,
                block,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        ocr_run = None
        if with_ocr:
            ocr_run = await _create_ocr_run(
                session,
                document_id=document.id,
                revision_id=revision.id,
                document_file_id=document_file.id,
                extraction_run_id=extraction_run.id,
                content_hash_character="d",
            )
            document_file.latest_ocr_run_id = ocr_run.id

        source_hash = calculate_source_snapshot_hash(
            extraction_run.content_hash,
            ocr_run.content_hash if ocr_run is not None else None,
        )
        previous_job = LanguageDetectionJob(
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            job_type=LanguageDetectionJobType.INITIAL_DETECTION,
            status=LanguageDetectionJobStatus.PERSISTING,
            progress=92,
            source_content_hash=source_hash,
            maximum_attempts=1,
        )
        session.add(previous_job)
        await session.flush()
        previous_run = await LanguagePersistenceService(
            session,
            config,
        ).persist_result(
            job=previous_job,
            result=_pipeline(
                extraction_run,
                container,
                block,
                config,
            ).model_copy(update={"source_content_hash": source_hash}),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        active_job = LanguageDetectionJob(
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            job_type=LanguageDetectionJobType.RE_DETECTION,
            status=LanguageDetectionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            source_content_hash=source_hash,
            maximum_attempts=1,
        )
        session.add(active_job)
        await session.commit()
        return SeededLanguageWorker(
            job_id=active_job.id,
            document_id=document.id,
            revision_id=revision.id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            latest_language_run_id=previous_run.id,
        )


def _worker_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> LanguageDetectionService:
    settings = get_settings()
    config = LanguageRuntimeConfig.from_settings(settings)
    detector = HybridLanguageDetector(
        FastTextLanguageDetector(
            Path("injected.bin"),
            predictor=EnglishPredictor(),
        ),
        config,
    )
    return LanguageDetectionService(
        settings,
        session_factory=session_factory,
        detector=detector,
    )


async def _replace_extraction(
    session_factory: async_sessionmaker[AsyncSession],
    seeded: SeededLanguageWorker,
) -> None:
    async with session_factory() as session:
        extraction_job = ExtractionJob(
            document_id=seeded.document_id,
            document_revision_id=seeded.revision_id,
            document_file_id=seeded.document_file_id,
            job_type=ExtractionJobType.RE_EXTRACTION,
            status=ExtractionJobStatus.COMPLETED,
            progress=100,
            maximum_attempts=1,
        )
        session.add(extraction_job)
        await session.flush()
        extraction_run = ExtractionRun(
            extraction_job_id=extraction_job.id,
            document_id=seeded.document_id,
            document_revision_id=seeded.revision_id,
            document_file_id=seeded.document_file_id,
            extractor_type=ExtractorType.PDF,
            extractor_version="test",
            status=ExtractionRunStatus.COMPLETED,
            source_sha256_hash="a" * 64,
            source_file_size=1234,
            content_hash="e" * 64,
            total_pages=1,
            total_blocks=1,
            total_characters=20,
            total_words=3,
            has_selectable_text=True,
            requires_ocr=False,
            warnings_json=[],
        )
        session.add(extraction_run)
        await session.flush()
        document_file = await session.get(
            DocumentFile,
            seeded.document_file_id,
        )
        assert document_file is not None
        document_file.latest_extraction_run_id = extraction_run.id
        await session.commit()


async def _replace_ocr(
    session_factory: async_sessionmaker[AsyncSession],
    seeded: SeededLanguageWorker,
) -> None:
    async with session_factory() as session:
        run = await _create_ocr_run(
            session,
            document_id=seeded.document_id,
            revision_id=seeded.revision_id,
            document_file_id=seeded.document_file_id,
            extraction_run_id=seeded.extraction_run_id,
            content_hash_character="e",
        )
        document_file = await session.get(
            DocumentFile,
            seeded.document_file_id,
        )
        assert document_file is not None
        document_file.latest_ocr_run_id = run.id
        await session.commit()


async def _assert_stale_job_failed_without_latest_overwrite(
    session_factory: async_sessionmaker[AsyncSession],
    seeded: SeededLanguageWorker,
) -> LanguageDetectionDocumentRow:
    async with session_factory() as session:
        job = await session.get(LanguageDetectionJob, seeded.job_id)
        document_file = await session.get(
            DocumentFile,
            seeded.document_file_id,
        )
        run_count = int(
            await session.scalar(
                select(func.count(LanguageDetectionRun.id)).where(
                    LanguageDetectionRun.document_file_id == seeded.document_file_id
                )
            )
            or 0
        )
        assert job is not None
        assert job.status is LanguageDetectionJobStatus.FAILED
        assert job.error_code == "LANGUAGE_SOURCE_CHANGED"
        assert job.error_message is not None
        assert "Queue a new job" in job.error_message
        assert document_file is not None
        assert (
            document_file.latest_language_detection_run_id
            == seeded.latest_language_run_id
        )
        latest = await LanguageDetectionRunRepository(session).get_latest_by_file(
            seeded.document_file_id
        )
        assert latest is None
        assert run_count == 1
        inventory_rows, inventory_total = await LanguageDetectionDocumentRepository(
            session
        ).list(
            search=None,
            department_id=None,
            language_status=None,
            not_started=False,
            scope_all_departments=True,
            scope_department_id=None,
            page=1,
            page_size=20,
            sort_by="documentCode",
            sort_order="asc",
        )
        assert inventory_total == 1
        assert len(inventory_rows) == 1
        inventory_row = inventory_rows[0]
        assert inventory_row.language_status is None
        assert inventory_row.language_progress is None
        assert inventory_row.language_current_stage is None
        assert inventory_row.language_active is False
        inventory_item = LanguageDetectionDocumentService._item(
            inventory_row,
            effective_ocr_block_count=0,
        )
        assert inventory_item.language_detection_run_id is None
        assert inventory_item.language_presence is None
        with pytest.raises(
            ValueError,
            match="source is no longer current",
        ):
            await LanguageDetectionRunRepository(session).set_latest_by_ids(
                document_file_id=seeded.document_file_id,
                language_detection_run_id=(seeded.latest_language_run_id),
            )
        await session.rollback()
        return inventory_row


@pytest.mark.asyncio
async def test_prepare_rejects_source_replaced_before_worker_start(
    session_factory,
) -> None:
    seeded = await _seed_worker(session_factory, with_ocr=False)
    await _replace_extraction(session_factory, seeded)

    status = await _worker_service(session_factory).process_job(
        seeded.job_id,
        worker_reference="pytest-language",
    )

    assert status is LanguageDetectionJobStatus.FAILED
    await _assert_stale_job_failed_without_latest_overwrite(
        session_factory,
        seeded,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("source_change", ["RE_EXTRACTION", "RE_OCR"])
async def test_pre_persist_guard_rejects_source_race_and_preserves_latest(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
    source_change: str,
) -> None:
    seeded = await _seed_worker(
        session_factory,
        with_ocr=True,
    )
    service = _worker_service(session_factory)
    persist = service._persist
    race_injected = False

    async def inject_source_change(job_id, result):
        nonlocal race_injected
        race_injected = True
        if source_change == "RE_EXTRACTION":
            await _replace_extraction(session_factory, seeded)
        else:
            await _replace_ocr(session_factory, seeded)
        return await persist(job_id, result)

    monkeypatch.setattr(service, "_persist", inject_source_change)
    status = await service.process_job(
        seeded.job_id,
        worker_reference="pytest-language",
    )

    assert race_injected is True
    assert status is LanguageDetectionJobStatus.FAILED
    inventory_row = await _assert_stale_job_failed_without_latest_overwrite(
        session_factory,
        seeded,
    )
    assert inventory_row.ocr_status is (
        None if source_change == "RE_EXTRACTION" else OCRJobStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_partial_extraction_requiring_ocr_cannot_be_queued_without_it(
    create_user,
    session_factory,
) -> None:
    user = await create_user(
        name="Partial Scan Admin",
        email="partial.scan.admin@example.com",
        role=UserRole.SUPER_ADMIN,
    )
    (
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
        block,
    ) = _source_graph()
    extraction_job.status = ExtractionJobStatus.PARTIALLY_COMPLETED
    extraction_run.status = ExtractionRunStatus.PARTIALLY_COMPLETED
    extraction_run.requires_ocr = True
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                container,
                block,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        await session.commit()

        with pytest.raises(ApplicationError) as raised:
            await LanguageDetectionJobService(
                session,
                get_settings(),
                user,
                RequestMetadata(ip_address=None, user_agent="pytest"),
                model_ready=True,
            ).start(
                document_file_id=document_file.id,
                extraction_run_id=extraction_run.id,
                ocr_run_id=None,
                force=False,
            )

    assert raised.value.status_code == 400
    assert raised.value.errors is not None
    assert raised.value.errors[0].field == "ocrRunId"


def test_inventory_marks_partial_scan_without_ocr_not_ready() -> None:
    (
        _document,
        _revision,
        document_file,
        _extraction_job,
        extraction_run,
        _container,
        _block,
    ) = _source_graph()
    extraction_run.status = ExtractionRunStatus.PARTIALLY_COMPLETED
    extraction_run.requires_ocr = True
    document_file.document.id = uuid4()
    document_file.revision.id = uuid4()
    document_file.id = uuid4()
    extraction_run.id = uuid4()
    document_file.latest_extraction_run = extraction_run
    document_file.latest_ocr_run = None
    document_file.latest_language_detection_run = None
    row = LanguageDetectionDocumentRow(
        document_file=document_file,
        extraction_status=ExtractionJobStatus.PARTIALLY_COMPLETED,
        ocr_status=None,
        language_status=None,
        language_progress=None,
        language_current_stage=None,
        language_active=False,
        native_block_count=1,
        ocr_block_count=0,
    )

    item = LanguageDetectionDocumentService._item(row)

    assert item.source_ready is False
    assert item.ocr_run_id is None
