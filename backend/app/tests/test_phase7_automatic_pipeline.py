"""Automatic Phase 7 chaining remains optional, durable, and idempotent."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.authorization import AuditAction
from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
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
)
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import (
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_page_result import OCRPageResult, OCRPageStatus
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.services.automatic_pipeline_service import (
    AutomaticPipelineService,
)
from app.services.language.language_normalizer import (
    calculate_source_snapshot_hash,
)
from app.workers import extraction_tasks, ocr_tasks


def _settings(**updates):
    return get_settings().model_copy(
        update={
            "auto_run_ocr_after_extraction": False,
            "auto_run_language_detection_after_extraction": False,
            "auto_run_language_detection_after_ocr": False,
            **updates,
        }
    )


async def _source_graph(
    session_factory,
    *,
    status: ExtractionJobStatus,
    requested_by: UUID | None = None,
    requires_ocr: bool | None = None,
) -> tuple[UUID, UUID, UUID]:
    source_key = uuid4().hex
    needs_ocr = (
        status is ExtractionJobStatus.OCR_REQUIRED
        if requires_ocr is None
        else requires_ocr
    )
    is_partial_scan = status is ExtractionJobStatus.PARTIALLY_COMPLETED and needs_ocr
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number=uuid4().hex[:8],
        base_document_code=f"MTI-OPS-POL-{uuid4().hex[:8].upper()}",
        title="Automatic Pipeline Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code=f"{document.base_document_code}_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="automatic-pipeline.pdf",
        sanitized_filename="automatic-pipeline.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=128,
        sha256_hash="a" * 64,
        storage_key=f"documents/originals/{source_key}.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    extraction_job = ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=status,
        progress=100,
        requested_by=requested_by,
    )
    run_status = ExtractionRunStatus(status.value)
    extraction_run = ExtractionRun(
        extraction_job=extraction_job,
        document=document,
        revision=revision,
        document_file=document_file,
        extractor_type=ExtractorType.PDF,
        extractor_version="1.0",
        status=run_status,
        source_sha256_hash=document_file.sha256_hash,
        source_file_size=document_file.file_size,
        content_hash="b" * 64,
        total_pages=2 if is_partial_scan else 1,
        total_blocks=(0 if status is ExtractionJobStatus.OCR_REQUIRED else 1),
        total_characters=(0 if status is ExtractionJobStatus.OCR_REQUIRED else 64),
        total_words=(0 if status is ExtractionJobStatus.OCR_REQUIRED else 9),
        has_selectable_text=(status is not ExtractionJobStatus.OCR_REQUIRED),
        requires_ocr=needs_ocr,
        warnings_json=[],
        metadata_json=(
            {"scannedPages": [2 if is_partial_scan else 1]} if needs_ocr else {}
        ),
    )
    text = (
        ""
        if status is ExtractionJobStatus.OCR_REQUIRED
        else "This policy applies to every department and document owner."
    )
    container = ExtractedContainer(
        extraction_run=extraction_run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=1,
        name="Page 1",
        raw_text=text,
        normalised_text=text,
        character_count=len(text),
        word_count=len(text.split()),
    )
    models: list[object] = [
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
    ]
    if text:
        models.append(
            ExtractedBlock(
                extraction_run=extraction_run,
                container=container,
                block_type=ExtractedBlockType.TEXT,
                block_order=1,
                source_reference="PDF:page=1:block=1",
                text=text,
                normalised_text=text,
                character_count=len(text),
                word_count=len(text.split()),
            )
        )
    async with session_factory() as session:
        session.add_all(models)
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        await session.commit()
    return extraction_job.id, extraction_run.id, document_file.id


async def _complete_ocr_job(
    session_factory,
    *,
    ocr_job_id: UUID,
    extraction_run_id: UUID,
    document_file_id: UUID,
    run_status: OCRRunStatus,
    with_block: bool,
) -> UUID:
    async with session_factory() as session:
        job = await session.get(OCRJob, ocr_job_id)
        extraction_run = await session.get(
            ExtractionRun,
            extraction_run_id,
        )
        document_file = await session.get(DocumentFile, document_file_id)
        assert job is not None
        assert extraction_run is not None
        assert document_file is not None
        job.status = OCRJobStatus(run_status.value)
        job.progress = 100
        ocr_run = OCRRun(
            ocr_job_id=job.id,
            document_id=job.document_id,
            document_revision_id=job.document_revision_id,
            document_file_id=job.document_file_id,
            source_extraction_run_id=extraction_run.id,
            provider="paddleocr",
            provider_version="3.7.0",
            language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
            status=run_status,
            source_sha256_hash=document_file.sha256_hash,
            page_count_requested=1,
            page_count_processed=1,
            page_count_failed=(
                1 if run_status is OCRRunStatus.PARTIALLY_COMPLETED else 0
            ),
            total_blocks=1 if with_block else 0,
            total_characters=22 if with_block else 0,
            render_dpi=300,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            content_hash="c" * 64,
            warnings_json=[],
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(ocr_run)
        await session.flush()
        if with_block:
            page = OCRPageResult(
                ocr_run_id=ocr_run.id,
                page_number=1,
                status=OCRPageStatus.COMPLETED,
                language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
                render_width=1000,
                render_height=1400,
                render_dpi=300,
                rotation_applied=0,
                block_count=1,
                character_count=22,
                raw_text="Automatic OCR content",
                normalised_text="Automatic OCR content",
                content_hash="d" * 64,
                warning_codes_json=[],
            )
            session.add(page)
            await session.flush()
            session.add(
                OCRBlock(
                    ocr_run_id=ocr_run.id,
                    ocr_page_result_id=page.id,
                    block_order=1,
                    text="Automatic OCR content",
                    normalised_text="Automatic OCR content",
                    confidence=0.95,
                    polygon_json=[
                        [0.0, 0.0],
                        [100.0, 0.0],
                        [100.0, 20.0],
                        [0.0, 20.0],
                    ],
                    bbox_json={
                        "x": 0.0,
                        "y": 0.0,
                        "width": 100.0,
                        "height": 20.0,
                    },
                    provider_model="paddleocr-latin",
                    recognition_profile=(OCRLanguageProfile.AUTO_MULTILINGUAL.value),
                    orientation=0,
                    character_count=22,
                )
            )
        document_file.latest_ocr_run_id = ocr_run.id
        await session.commit()
        return ocr_run.id


@pytest.mark.asyncio
async def test_automatic_pipeline_defaults_leave_phase6_result_unchanged(
    session_factory,
) -> None:
    extraction_job_id, _, _ = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.OCR_REQUIRED,
    )
    dispatched: list[UUID] = []
    service = AutomaticPipelineService(
        _settings(),
        session_factory=session_factory,
        ocr_dispatcher=lambda job_id: dispatched.append(job_id),
    )

    result = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.OCR_REQUIRED,
    )

    assert result is None
    assert dispatched == []
    async with session_factory() as session:
        assert await session.scalar(select(func.count(OCRJob.id))) == 0


@pytest.mark.asyncio
async def test_ocr_required_extraction_queues_once_and_reuses_attribution(
    session_factory,
    create_user,
) -> None:
    requester = await create_user(
        email="automatic.ocr@example.com",
    )
    extraction_job_id, extraction_run_id, document_file_id = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.OCR_REQUIRED,
        requested_by=requester.id,
    )
    dispatched: list[UUID] = []

    async def dispatch(job_id: UUID) -> str:
        dispatched.append(job_id)
        return "automatic-ocr-task"

    service = AutomaticPipelineService(
        _settings(auto_run_ocr_after_extraction=True),
        session_factory=session_factory,
        ocr_dispatcher=dispatch,
    )
    created = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.OCR_REQUIRED,
    )
    duplicate = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.OCR_REQUIRED,
    )

    assert created is not None
    assert duplicate is None
    assert dispatched == [created]
    async with session_factory() as session:
        job = await session.get(OCRJob, created)
        audits = list(
            await session.scalars(
                select(AuditLog).where(AuditLog.action == AuditAction.QUEUE_OCR)
            )
        )
        assert job is not None
        assert job.extraction_run_id == extraction_run_id
        assert job.requested_by == requester.id
        assert job.worker_reference == "automatic-ocr-task"
        assert job.requested_page_numbers_json == [1]
        assert len(audits) == 1
        assert audits[0].user_id == requester.id
        assert audits[0].new_values_json["automatic"] is True

    await _complete_ocr_job(
        session_factory,
        ocr_job_id=created,
        extraction_run_id=extraction_run_id,
        document_file_id=document_file_id,
        run_status=OCRRunStatus.COMPLETED,
        with_block=False,
    )
    completed_duplicate = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.OCR_REQUIRED,
    )
    assert completed_duplicate is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count(OCRJob.id))) == 1


@pytest.mark.asyncio
async def test_partial_scan_queues_ocr_before_language_detection(
    session_factory,
) -> None:
    extraction_job_id, extraction_run_id, _ = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.PARTIALLY_COMPLETED,
        requires_ocr=True,
    )
    language_dispatched: list[UUID] = []
    language_only = AutomaticPipelineService(
        _settings(auto_run_language_detection_after_extraction=True),
        session_factory=session_factory,
        language_dispatcher=lambda job_id: (
            language_dispatched.append(job_id) or "unexpected-language-task"
        ),
    )

    skipped_language = await language_only.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
    )

    assert skipped_language is None
    assert language_dispatched == []

    ocr_dispatched: list[UUID] = []
    service = AutomaticPipelineService(
        _settings(
            auto_run_ocr_after_extraction=True,
            auto_run_language_detection_after_extraction=True,
        ),
        session_factory=session_factory,
        ocr_dispatcher=lambda job_id: (
            ocr_dispatched.append(job_id) or "partial-scan-ocr-task"
        ),
    )
    created = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
    )

    assert created is not None
    assert ocr_dispatched == [created]
    async with session_factory() as session:
        job = await session.get(OCRJob, created)
        assert job is not None
        assert job.extraction_run_id == extraction_run_id
        assert job.requested_page_numbers_json == [2]
        assert await session.scalar(select(func.count(LanguageDetectionJob.id))) == 0


@pytest.mark.asyncio
async def test_automatic_ocr_honours_per_user_concurrency_limit(
    session_factory,
    create_user,
) -> None:
    requester = await create_user(email="automatic.ocr.limit@example.com")
    first_source, _, _ = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.OCR_REQUIRED,
        requested_by=requester.id,
    )
    second_source, _, _ = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.OCR_REQUIRED,
        requested_by=requester.id,
    )
    dispatched: list[UUID] = []
    service = AutomaticPipelineService(
        _settings(
            auto_run_ocr_after_extraction=True,
            ocr_max_concurrent_jobs_per_user=1,
        ),
        session_factory=session_factory,
        ocr_dispatcher=lambda job_id: dispatched.append(job_id) or "limited-ocr-task",
    )

    first = await service.after_extraction(
        first_source,
        ExtractionJobStatus.OCR_REQUIRED,
    )
    second = await service.after_extraction(
        second_source,
        ExtractionJobStatus.OCR_REQUIRED,
    )

    assert first is not None
    assert second is None
    assert dispatched == [first]
    async with session_factory() as session:
        assert await session.scalar(select(func.count(OCRJob.id))) == 1


@pytest.mark.asyncio
async def test_automatic_dispatch_failure_is_audited_without_rewriting_source(
    session_factory,
) -> None:
    extraction_job_id, _, _ = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.OCR_REQUIRED,
    )

    def unavailable_dispatcher(_job_id: UUID) -> None:
        raise ConnectionError("test broker unavailable")

    service = AutomaticPipelineService(
        _settings(auto_run_ocr_after_extraction=True),
        session_factory=session_factory,
        ocr_dispatcher=unavailable_dispatcher,
    )
    downstream_job_id = await service.after_extraction(
        extraction_job_id,
        ExtractionJobStatus.OCR_REQUIRED,
    )

    assert downstream_job_id is not None
    async with session_factory() as session:
        source = await session.get(ExtractionJob, extraction_job_id)
        downstream = await session.get(OCRJob, downstream_job_id)
        failure_audit = await session.scalar(
            select(AuditLog).where(AuditLog.action == AuditAction.FAIL_OCR)
        )
        assert source is not None
        assert source.status is ExtractionJobStatus.OCR_REQUIRED
        assert downstream is not None
        assert downstream.status is OCRJobStatus.FAILED
        assert downstream.error_code == "OCR_PROVIDER_UNAVAILABLE"
        assert failure_audit is not None
        assert failure_audit.new_values_json["automatic"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ExtractionJobStatus.COMPLETED,
        ExtractionJobStatus.PARTIALLY_COMPLETED,
    ],
)
async def test_extraction_queues_one_native_language_job(
    session_factory,
    status: ExtractionJobStatus,
) -> None:
    extraction_job_id, extraction_run_id, document_file_id = await _source_graph(
        session_factory, status=status
    )
    dispatched: list[UUID] = []
    service = AutomaticPipelineService(
        _settings(
            auto_run_language_detection_after_extraction=True,
        ),
        session_factory=session_factory,
        language_dispatcher=lambda job_id: (
            dispatched.append(job_id) or "automatic-language-task"
        ),
    )

    created = await service.after_extraction(
        extraction_job_id,
        status,
    )
    duplicate = await service.after_extraction(
        extraction_job_id,
        status,
    )

    assert created is not None
    assert duplicate is None
    assert dispatched == [created]
    async with session_factory() as session:
        job = await session.get(LanguageDetectionJob, created)
        assert job is not None
        assert job.extraction_run_id == extraction_run_id
        assert job.ocr_run_id is None
        assert job.worker_reference == "automatic-language-task"
        assert (
            job.result_summary_json["automaticPipeline"]["trigger"]
            == "EXTRACTION_COMPLETED"
        )
        queue_audits = list(
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.QUEUE_LANGUAGE_DETECTION
                )
            )
        )
        assert len(queue_audits) == 1
        assert queue_audits[0].user_id is None
        assert queue_audits[0].new_values_json["automatic"] is True

        job.status = LanguageDetectionJobStatus.COMPLETED
        job.progress = 100
        source_hash = calculate_source_snapshot_hash(
            "b" * 64,
            None,
        )
        session.add(
            LanguageDetectionRun(
                document_id=job.document_id,
                document_revision_id=job.document_revision_id,
                document_file_id=document_file_id,
                extraction_run_id=extraction_run_id,
                ocr_run_id=None,
                job_id=job.id,
                detector_name="hybrid",
                detector_version="1.0",
                status=LanguageDetectionRunStatus.COMPLETED,
                source_content_hash=source_hash,
                total_blocks=1,
                eligible_blocks=1,
                detected_blocks=1,
                unknown_blocks=0,
                mixed_blocks=0,
                indonesian_blocks=0,
                english_blocks=1,
                chinese_blocks=0,
                other_blocks=0,
                total_characters=64,
                indonesian_characters=0,
                english_characters=64,
                chinese_characters=0,
                mixed_characters=0,
                unknown_characters=0,
                average_confidence=0.95,
                warnings_json=[],
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()

    completed_duplicate = await service.after_extraction(
        extraction_job_id,
        status,
    )
    assert completed_duplicate is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count(LanguageDetectionJob.id))) == 1


@pytest.mark.asyncio
async def test_partial_ocr_queues_one_merged_language_job(
    session_factory,
) -> None:
    extraction_job_id, extraction_run_id, document_file_id = await _source_graph(
        session_factory,
        status=ExtractionJobStatus.PARTIALLY_COMPLETED,
    )
    async with session_factory() as session:
        extraction_job = await session.get(
            ExtractionJob,
            extraction_job_id,
        )
        assert extraction_job is not None
        ocr_job = OCRJob(
            document_id=extraction_job.document_id,
            document_revision_id=extraction_job.document_revision_id,
            document_file_id=document_file_id,
            extraction_run_id=extraction_run_id,
            job_type=OCRJobType.INITIAL_OCR,
            status=OCRJobStatus.PARTIALLY_COMPLETED,
            progress=100,
            language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            requested_page_numbers_json=[1],
            processed_page_numbers_json=[1],
            failed_page_numbers_json=[],
            provider="paddleocr",
            maximum_attempts=2,
        )
        session.add(ocr_job)
        await session.commit()
        ocr_job_id = ocr_job.id
    ocr_run_id = await _complete_ocr_job(
        session_factory,
        ocr_job_id=ocr_job_id,
        extraction_run_id=extraction_run_id,
        document_file_id=document_file_id,
        run_status=OCRRunStatus.PARTIALLY_COMPLETED,
        with_block=True,
    )
    dispatched: list[UUID] = []
    service = AutomaticPipelineService(
        _settings(auto_run_language_detection_after_ocr=True),
        session_factory=session_factory,
        language_dispatcher=lambda job_id: (
            dispatched.append(job_id) or "language-after-ocr"
        ),
    )

    created = await service.after_ocr(
        ocr_job_id,
        OCRJobStatus.PARTIALLY_COMPLETED,
    )
    duplicate = await service.after_ocr(
        ocr_job_id,
        OCRJobStatus.PARTIALLY_COMPLETED,
    )

    assert created is not None
    assert duplicate is None
    assert dispatched == [created]
    async with session_factory() as session:
        job = await session.get(LanguageDetectionJob, created)
        assert job is not None
        assert job.ocr_run_id == ocr_run_id
        assert job.extraction_run_id == extraction_run_id
        assert (
            job.result_summary_json["automaticPipeline"]["trigger"] == "OCR_COMPLETED"
        )


def test_worker_hooks_do_not_replace_committed_source_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_calls: list[tuple[UUID, ExtractionJobStatus]] = []
    ocr_calls: list[tuple[UUID, OCRJobStatus]] = []

    class FakeExtractionService:
        def __init__(self, _settings) -> None:
            pass

        async def process_job(self, job_id: UUID, **_kwargs):
            return ExtractionJobStatus.COMPLETED

    class FakeOCRService:
        def __init__(self, _settings) -> None:
            pass

        async def process_job(self, job_id: UUID, **_kwargs):
            return OCRJobStatus.COMPLETED

    class FakeExtractionPipeline:
        def __init__(self, _settings) -> None:
            pass

        async def after_extraction(
            self,
            job_id: UUID,
            status: ExtractionJobStatus,
        ) -> None:
            extraction_calls.append((job_id, status))
            raise RuntimeError("optional pipeline unavailable")

    class FakeOCRPipeline:
        def __init__(self, _settings) -> None:
            pass

        async def after_ocr(
            self,
            job_id: UUID,
            status: OCRJobStatus,
        ) -> None:
            ocr_calls.append((job_id, status))
            raise RuntimeError("optional pipeline unavailable")

    monkeypatch.setattr(
        extraction_tasks,
        "ExtractionService",
        FakeExtractionService,
    )
    monkeypatch.setattr(
        extraction_tasks,
        "AutomaticPipelineService",
        FakeExtractionPipeline,
    )
    monkeypatch.setattr(ocr_tasks, "OCRService", FakeOCRService)
    monkeypatch.setattr(
        ocr_tasks,
        "AutomaticPipelineService",
        FakeOCRPipeline,
    )
    extraction_job_id = uuid4()
    ocr_job_id = uuid4()

    extraction_result = extraction_tasks.process_extraction_job.run(
        str(extraction_job_id)
    )
    ocr_result = ocr_tasks.process_ocr_job.run(str(ocr_job_id))

    assert extraction_result["status"] == ExtractionJobStatus.COMPLETED
    assert ocr_result["status"] == OCRJobStatus.COMPLETED
    assert extraction_calls == [(extraction_job_id, ExtractionJobStatus.COMPLETED)]
    assert ocr_calls == [(ocr_job_id, OCRJobStatus.COMPLETED)]
