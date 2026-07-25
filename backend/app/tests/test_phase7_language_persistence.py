"""Focused transactional repository tests for Phase 7 language results."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.authorization import AuditAction, UserRole
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
from app.models.language_block_result import (
    LanguageCode,
    LanguageSourceType,
)
from app.models.language_detection_job import (
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.repositories.language_container_summary_repository import (
    LanguageContainerSummaryRepository,
)
from app.repositories.language_detection_job_repository import (
    LanguageDetectionJobRepository,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.schemas.language_internal import (
    DetectedLanguageBlockData,
    LanguagePipelineResultData,
    LanguageSourceBlockData,
)
from app.services.language.fasttext_language_detector import (
    FastTextLanguageDetector,
)
from app.services.language.hybrid_language_detector import (
    HybridLanguageDetector,
)
from app.services.language.language_aggregation_service import (
    LanguageAggregationService,
)
from app.services.language.language_detection_job_service import (
    LanguageDetectionJobService,
)
from app.services.language.language_persistence_service import (
    LanguagePersistenceService,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)


class EnglishPredictor:
    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]:
        del text, k
        return ["__label__en", "__label__id"], [0.94, 0.02]


def _source_graph() -> tuple[
    Document,
    DocumentRevision,
    DocumentFile,
    ExtractionJob,
    ExtractionRun,
    ExtractedContainer,
    ExtractedBlock,
]:
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number="007",
        base_document_code="MTI-HRM-POL-007",
        title="Language Persistence Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-HRM-POL-007_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="MTI-HRM-POL-007_Rev.000.pdf",
        sanitized_filename="MTI-HRM-POL-007_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=1234,
        sha256_hash="a" * 64,
        storage_key="documents/originals/phase7/language.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    extraction_job = ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=ExtractionJobStatus.COMPLETED,
        progress=100,
        maximum_attempts=1,
    )
    extraction_run = ExtractionRun(
        extraction_job=extraction_job,
        document=document,
        revision=revision,
        document_file=document_file,
        extractor_type=ExtractorType.PDF,
        extractor_version="1.0",
        status=ExtractionRunStatus.COMPLETED,
        source_sha256_hash="a" * 64,
        source_file_size=1234,
        content_hash="b" * 64,
        total_pages=1,
        total_blocks=1,
        total_characters=63,
        total_words=10,
        has_selectable_text=True,
        requires_ocr=False,
        warnings_json=[],
    )
    container = ExtractedContainer(
        extraction_run=extraction_run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=1,
        name="Page 1",
        raw_text=(
            "This document shall apply to every department and reviewer."
        ),
        normalised_text=(
            "This document shall apply to every department and reviewer."
        ),
        character_count=63,
        word_count=10,
    )
    block = ExtractedBlock(
        extraction_run=extraction_run,
        container=container,
        block_type=ExtractedBlockType.TEXT,
        block_order=1,
        source_reference="PDF:page=1:block=1",
        text="This document shall apply to every department and reviewer.",
        normalised_text=(
            "This document shall apply to every department and reviewer."
        ),
        character_count=63,
        word_count=10,
    )
    return (
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
        block,
    )


def _pipeline(
    extraction_run: ExtractionRun,
    container: ExtractedContainer,
    block: ExtractedBlock,
    config: LanguageRuntimeConfig,
) -> LanguagePipelineResultData:
    detector = HybridLanguageDetector(
        FastTextLanguageDetector(
            Path("injected.bin"),
            predictor=EnglishPredictor(),
        ),
        config,
    )
    source = LanguageSourceBlockData(
        source_type=LanguageSourceType.NATIVE_EXTRACTION,
        extracted_block_id=block.id,
        ocr_block_id=None,
        container_id=container.id,
        container_type=container.container_type.value,
        container_name=container.name,
        container_index=container.container_index,
        page_number=1,
        block_order=block.block_order,
        source_reference=block.source_reference,
        text=block.text,
        normalised_text=block.normalised_text,
    )
    detected = DetectedLanguageBlockData(
        source=source,
        detection=detector.detect(source.text),
    )
    aggregation = LanguageAggregationService(config)
    return LanguagePipelineResultData(
        source_content_hash="c" * 64,
        blocks=[detected],
        containers=aggregation.aggregate_containers([detected]),
        aggregate=aggregation.aggregate([detected]),
        detector_name="hybrid-unicode-fasttext",
        detector_version="1.0",
    )


def _language_job(
    document: Document,
    revision: DocumentRevision,
    document_file: DocumentFile,
    extraction_run: ExtractionRun,
) -> LanguageDetectionJob:
    return LanguageDetectionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        extraction_run_id=extraction_run.id,
        job_type=LanguageDetectionJobType.INITIAL_DETECTION,
        status=LanguageDetectionJobStatus.PERSISTING,
        progress=92,
        source_content_hash="c" * 64,
        maximum_attempts=1,
    )


@pytest.mark.asyncio
async def test_language_persistence_keeps_history_and_updates_latest(
    session_factory,
) -> None:
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
        await session.commit()
        first_job = _language_job(
            document,
            revision,
            document_file,
            extraction_run,
        )
        session.add(first_job)
        await session.flush()
        first_run = await LanguagePersistenceService(
            session,
            config,
        ).persist_result(
            job=first_job,
            result=_pipeline(
                extraction_run,
                container,
                block,
                config,
            ),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        await session.commit()

        latest = await LanguageDetectionRunRepository(
            session
        ).get_latest_by_file(document_file.id)
        assert latest is not None
        assert latest.id == first_run.id
        assert first_job.status is LanguageDetectionJobStatus.COMPLETED
        rows, total = await LanguageBlockResultRepository(session).list(
            first_run.id
        )
        assert total == 1
        assert rows[0].text.startswith("This document")
        assert rows[0].result.language_code is LanguageCode.ENGLISH
        summaries, summary_total = await (
            LanguageContainerSummaryRepository(session).list(first_run.id)
        )
        assert summary_total == 1
        assert summaries[0].container_index == 1
        assert summaries[0].coverage_json["preliminary"] is True

        second_job = _language_job(
            document,
            revision,
            document_file,
            extraction_run,
        )
        second_job.job_type = LanguageDetectionJobType.RE_DETECTION
        second_job.reason = "Detector configuration updated."
        session.add(second_job)
        await session.flush()
        second_result = _pipeline(
            extraction_run,
            container,
            block,
            config,
        ).model_copy(update={"source_content_hash": "d" * 64})
        second_run = await LanguagePersistenceService(
            session,
            config,
        ).persist_result(
            job=second_job,
            result=second_result,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        await session.commit()

        latest = await LanguageDetectionRunRepository(
            session
        ).get_latest_by_file(document_file.id)
        history = await LanguageDetectionRunRepository(
            session
        ).list_by_file(document_file.id)
        assert latest is not None and latest.id == second_run.id
        assert {run.id for run in history} == {
            first_run.id,
            second_run.id,
        }


@pytest.mark.asyncio
async def test_language_api_queue_results_history_redetect_and_exports(
    api_client: AsyncClient,
    create_user,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    department_id = uuid4()
    controller = await create_user(
        name="Language Controller",
        email="language.controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department_id,
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
    document.department_id = department_id
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

    def model_is_ready(_: LanguageDetectionJobService) -> None:
        return None

    async def do_not_dispatch(
        _: LanguageDetectionJobService,
        __: LanguageDetectionJob,
    ) -> None:
        return None

    monkeypatch.setattr(
        LanguageDetectionJobService,
        "_ensure_model_ready",
        model_is_ready,
    )
    monkeypatch.setattr(
        LanguageDetectionJobService,
        "_dispatch",
        do_not_dispatch,
    )
    login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "language.controller@example.com",
            "password": "Valid123",
        },
    )
    assert login.status_code == 200
    headers = {
        "Authorization": (
            f"Bearer {login.json()['data']['accessToken']}"
        )
    }
    inventory_before_detection = await api_client.get(
        "/api/v1/language-detection/documents",
        params={"status": "NOT_STARTED"},
        headers=headers,
    )
    assert inventory_before_detection.status_code == 200
    inventory_before_data = inventory_before_detection.json()["data"]
    assert inventory_before_data["totalItems"] == 1
    undetected = inventory_before_data["items"][0]
    assert undetected["file"]["id"] == str(document_file.id)
    assert undetected["extractionStatus"] == "COMPLETED"
    assert undetected["ocrStatus"] is None
    assert undetected["languageDetectionStatus"] is None
    assert undetected["languageDetectionRunId"] is None
    assert undetected["languagePresence"] is None
    assert undetected["sourceReady"] is True
    assert undetected["extractionRunId"] == str(extraction_run.id)

    queued = await api_client.post(
        "/api/v1/language-detection/jobs",
        json={
            "documentFileId": str(document_file.id),
            "extractionRunId": str(extraction_run.id),
            "ocrRunId": None,
            "force": False,
        },
        headers=headers,
    )
    assert queued.status_code == 202, queued.text
    queued_data = queued.json()["data"]
    assert queued_data["status"] == "QUEUED"
    assert queued_data["reusedExistingResult"] is False
    active_inventory = await api_client.get(
        "/api/v1/language-detection/documents",
        headers=headers,
    )
    assert active_inventory.status_code == 200
    active_item = active_inventory.json()["data"]["items"][0]
    assert active_item["languageDetectionStatus"] == "QUEUED"
    assert active_item["languageProgress"] == 0
    assert active_item["sourceReady"] is False

    config = LanguageRuntimeConfig(database_batch_size=1)
    async with session_factory() as session:
        job = await LanguageDetectionJobRepository(session).get_by_id(
            UUID(queued_data["jobId"]),
            for_update=True,
        )
        assert job is not None and job.source_content_hash is not None
        job.status = LanguageDetectionJobStatus.PERSISTING
        job.progress = 92
        result = _pipeline(
            extraction_run,
            container,
            block,
            config,
        ).model_copy(
            update={"source_content_hash": job.source_content_hash}
        )
        run = await LanguagePersistenceService(
            session,
            config,
        ).persist_result(
            job=job,
            result=result,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        await session.commit()
        run_id = run.id

    inventory_after_detection = await api_client.get(
        "/api/v1/language-detection/documents",
        params={
            "search": "MTI-HRM-POL-007",
            "status": "COMPLETED",
        },
        headers=headers,
    )
    assert inventory_after_detection.status_code == 200
    inventory_item = inventory_after_detection.json()["data"]["items"][0]
    assert inventory_item["languageDetectionStatus"] == "COMPLETED"
    assert inventory_item["languageProgress"] == 100
    assert inventory_item["languageDetectionRunId"] == str(run_id)
    assert inventory_item["lastDetected"] is not None
    assert inventory_item["languagePresence"]["en"] == (
        "INSUFFICIENT_EVIDENCE"
    )
    assert inventory_item["sourceReady"] is True

    (
        awaiting_document,
        awaiting_revision,
        awaiting_file,
        awaiting_extraction_job,
        awaiting_extraction_run,
        awaiting_container,
        awaiting_block,
    ) = _source_graph()
    awaiting_document.department_id = department_id
    awaiting_document.document_number = "008"
    awaiting_document.base_document_code = "MTI-HRM-POL-008"
    awaiting_document.title = "Scanned Language Policy"
    awaiting_revision.full_document_code = "MTI-HRM-POL-008_Rev.000"
    awaiting_file.original_filename = "MTI-HRM-POL-008_Rev.000.pdf"
    awaiting_file.sanitized_filename = "MTI-HRM-POL-008_Rev.000.pdf"
    awaiting_file.storage_key = "documents/originals/phase7/awaiting-ocr.pdf"
    awaiting_extraction_job.status = ExtractionJobStatus.OCR_REQUIRED
    awaiting_extraction_run.status = ExtractionRunStatus.OCR_REQUIRED
    awaiting_extraction_run.requires_ocr = True
    async with session_factory() as session:
        session.add_all(
            [
                awaiting_document,
                awaiting_revision,
                awaiting_file,
                awaiting_extraction_job,
                awaiting_extraction_run,
                awaiting_container,
                awaiting_block,
            ]
        )
        await session.flush()
        awaiting_file.latest_extraction_run_id = awaiting_extraction_run.id
        await session.commit()

    (
        replaced_document,
        replaced_revision,
        replaced_file,
        replaced_extraction_job,
        replaced_extraction_run,
        replaced_container,
        replaced_block,
    ) = _source_graph()
    replaced_document.department_id = department_id
    replaced_document.document_number = "009"
    replaced_document.base_document_code = "MTI-HRM-POL-009"
    replaced_revision.full_document_code = "MTI-HRM-POL-009_Rev.000"
    replaced_file.original_filename = "MTI-HRM-POL-009_Rev.000.pdf"
    replaced_file.sanitized_filename = "MTI-HRM-POL-009_Rev.000.pdf"
    replaced_file.storage_key = "documents/originals/phase7/replaced.pdf"
    replaced_file.file_status = DocumentFileStatus.REPLACED
    replaced_file.is_current = False
    async with session_factory() as session:
        session.add_all(
            [
                replaced_document,
                replaced_revision,
                replaced_file,
                replaced_extraction_job,
                replaced_extraction_run,
                replaced_container,
                replaced_block,
            ]
        )
        await session.flush()
        replaced_file.latest_extraction_run_id = replaced_extraction_run.id
        await session.commit()

    complete_inventory = await api_client.get(
        "/api/v1/language-detection/documents",
        headers=headers,
    )
    assert complete_inventory.status_code == 200
    complete_items = {
        item["document"]["baseDocumentCode"]: item
        for item in complete_inventory.json()["data"]["items"]
    }
    assert set(complete_items) == {
        "MTI-HRM-POL-007",
        "MTI-HRM-POL-008",
    }
    awaiting_item = complete_items["MTI-HRM-POL-008"]
    assert awaiting_item["extractionStatus"] == "OCR_REQUIRED"
    assert awaiting_item["languageDetectionStatus"] is None
    assert awaiting_item["sourceReady"] is False

    run_response = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}",
        headers=headers,
    )
    assert run_response.status_code == 200, run_response.text
    run_data = run_response.json()["data"]
    assert run_data["isLatest"] is True
    assert run_data["englishBlocks"] == 1
    assert run_data["preliminaryLabel"] == "Preliminary Coverage"
    assert run_data["coverage"]["preliminary"] is True
    assert "final compliance" in run_data["coverage"]["disclaimer"]

    summary = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}/summary",
        headers=headers,
    )
    assert summary.status_code == 200
    assert summary.json()["data"]["languagePresence"]["en"] == (
        "INSUFFICIENT_EVIDENCE"
    )

    blocks = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}/blocks",
        params={"languageCode": "en", "sourceType": "NATIVE_EXTRACTION"},
        headers=headers,
    )
    assert blocks.status_code == 200, blocks.text
    block_data = blocks.json()["data"]
    assert block_data["totalItems"] == 1
    assert block_data["items"][0]["text"].startswith("This document")
    assert block_data["items"][0]["languageCode"] == "en"

    containers = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}/containers",
        headers=headers,
    )
    assert containers.status_code == 200
    assert containers.json()["data"]["items"][0]["containerIndex"] == 1

    history = await api_client.get(
        (
            f"/api/v1/document-files/{document_file.id}/"
            "language-detection-history"
        ),
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()["data"]["items"][0]["isLatest"] is True

    json_export = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}/export",
        params={"format": "json"},
        headers=headers,
    )
    assert json_export.status_code == 200, json_export.text
    exported = json_export.json()
    assert exported["run"]["runId"] == str(run_id)
    assert exported["blocks"][0]["languageCode"] == "en"

    xlsx_export = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}/export",
        params={"format": "xlsx"},
        headers=headers,
    )
    assert xlsx_export.status_code == 200, xlsx_export.text
    assert xlsx_export.content.startswith(b"PK")

    redetected = await api_client.post(
        f"/api/v1/language-detection/runs/{run_id}/redetect",
        json={"reason": "Language model configuration updated."},
        headers=headers,
    )
    assert redetected.status_code == 202, redetected.text
    assert redetected.json()["data"]["status"] == "QUEUED"
    cancelled = await api_client.post(
        (
            "/api/v1/language-detection/jobs/"
            f"{redetected.json()['data']['jobId']}/cancel"
        ),
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCEL_REQUESTED"
    async with session_factory() as session:
        audit_actions = set(
            await session.scalars(
                select(AuditLog.action).where(
                    AuditLog.entity_type.in_(
                        {
                            "LanguageDetectionJob",
                            "LanguageDetectionRun",
                        }
                    )
                )
            )
        )
    assert {
        AuditAction.QUEUE_LANGUAGE_DETECTION,
        AuditAction.EXPORT_LANGUAGE_RESULT,
        AuditAction.REDETECT_LANGUAGE,
        AuditAction.CANCEL_LANGUAGE_DETECTION,
    }.issubset(audit_actions)

    outsider = await create_user(
        name="Other Department",
        email="language.outsider@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=uuid4(),
    )
    assert outsider.id != controller.id
    outsider_login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "language.outsider@example.com",
            "password": "Valid123",
        },
    )
    outsider_headers = {
        "Authorization": (
            f"Bearer {outsider_login.json()['data']['accessToken']}"
        )
    }
    denied = await api_client.get(
        f"/api/v1/language-detection/runs/{run_id}",
        headers=outsider_headers,
    )
    assert denied.status_code == 404
    scoped_inventory = await api_client.get(
        "/api/v1/language-detection/documents",
        headers=outsider_headers,
    )
    assert scoped_inventory.status_code == 200
    assert scoped_inventory.json()["data"]["totalItems"] == 0
