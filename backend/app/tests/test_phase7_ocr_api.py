"""Phase 7 OCR API contracts, authorization, exports, and history tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction, UserRole
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
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
from app.services.auth.token_service import TokenService
from app.services.ocr.ocr_job_service import OCRJobService

TestSessionFactory = async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class OCRSource:
    """Identifiers for one persisted PDF extraction source."""

    department_id: UUID
    document_id: UUID
    revision_id: UUID
    file_id: UUID
    extraction_run_id: UUID
    document_code: str


@dataclass(frozen=True, slots=True)
class PersistedOCR:
    """Identifiers for one persisted OCR result graph."""

    job_id: UUID
    run_id: UUID


def _headers(user: Any, token_service: TokenService) -> dict[str, str]:
    token = token_service.create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def _seed_department(
    session_factory: TestSessionFactory,
    *,
    code: str,
) -> Department:
    async with session_factory() as session:
        department = Department(
            code=code,
            name=f"{code} Department",
        )
        session.add(department)
        await session.commit()
        return department


async def _seed_ocr_source(
    session_factory: TestSessionFactory,
    *,
    department: Department,
    uploaded_by: UUID,
    number: int,
) -> OCRSource:
    """Persist a two-page scanned-PDF extraction eligible for OCR."""

    suffix = f"{number:03d}"
    source = f"phase-7-ocr-source-{suffix}".encode()
    source_hash = hashlib.sha256(source).hexdigest()
    async with session_factory() as session:
        document_type = DocumentType(
            code=f"O{suffix}",
            name=f"OCR Procedure {suffix}",
            requires_section=False,
        )
        document_status = DocumentStatus(
            code=f"R{suffix}",
            name=f"Released {suffix}",
            is_initial=False,
            display_order=number,
        )
        session.add_all([document_type, document_status])
        await session.flush()

        document_code = f"MTI-{department.code}-SOP-{suffix}"
        document = Document(
            company_code="MTI",
            department_id=department.id,
            document_type_id=document_type.id,
            document_number=suffix,
            base_document_code=document_code,
            title=f"Phase 7 OCR Procedure {suffix}",
        )
        revision = DocumentRevision(
            document=document,
            revision_code="Rev.000",
            revision_number=0,
            full_document_code=f"{document_code}_Rev.000",
            document_status_id=document_status.id,
            is_current=True,
        )
        document.current_revision = revision
        document_file = DocumentFile(
            document=document,
            revision=revision,
            original_filename=f"{document_code}_Rev.000.pdf",
            sanitized_filename=f"{document_code}_Rev.000.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size=len(source),
            sha256_hash=source_hash,
            storage_provider="local",
            storage_key=f"documents/originals/tests/phase7/{suffix}.pdf",
            file_status=DocumentFileStatus.AVAILABLE,
            is_primary=True,
            is_current=True,
            uploaded_by=uploaded_by,
        )
        extraction_job = ExtractionJob(
            document=document,
            revision=revision,
            document_file=document_file,
            job_type=ExtractionJobType.INITIAL_EXTRACTION,
            status=ExtractionJobStatus.OCR_REQUIRED,
            progress=100,
            current_stage="OCR required",
            requested_by=uploaded_by,
        )
        extraction_run = ExtractionRun(
            extraction_job=extraction_job,
            document=document,
            revision=revision,
            document_file=document_file,
            extractor_type=ExtractorType.PDF,
            extractor_version="phase7-api-test",
            status=ExtractionRunStatus.OCR_REQUIRED,
            source_sha256_hash=source_hash,
            source_file_size=len(source),
            total_pages=2,
            total_characters=0,
            has_selectable_text=False,
            requires_ocr=True,
            warnings_json=[],
            metadata_json={"scannedPages": [1, 2]},
        )
        containers = [
            ExtractedContainer(
                extraction_run=extraction_run,
                container_type=ExtractedContainerType.PDF_PAGE,
                container_index=page_number,
                name=f"Page {page_number}",
                raw_text="",
                normalised_text="",
                character_count=0,
                word_count=0,
            )
            for page_number in (1, 2)
        ]
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                *containers,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        await session.commit()
        return OCRSource(
            department_id=department.id,
            document_id=document.id,
            revision_id=revision.id,
            file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            document_code=document_code,
        )


def _page_blocks(page_number: int, variant: str) -> list[tuple[str, float, int]]:
    if page_number == 1:
        return [
            (f"Kebijakan pengendalian dokumen {variant}", 0.95, 0),
            (f"Manual review required {variant}", 0.45, 0),
        ]
    return [(f"文件控制程序 {variant}", 0.70, 90)]


async def _seed_completed_ocr(
    session_factory: TestSessionFactory,
    *,
    source: OCRSource,
    requested_by: UUID,
    created_at: datetime,
    variant: str,
    job_type: OCRJobType = OCRJobType.INITIAL_OCR,
    reason: str | None = None,
) -> PersistedOCR:
    """Persist a completed OCR run with pages and geometric text blocks."""

    async with session_factory() as session:
        job = OCRJob(
            document_id=source.document_id,
            document_revision_id=source.revision_id,
            document_file_id=source.file_id,
            extraction_run_id=source.extraction_run_id,
            job_type=job_type,
            status=OCRJobStatus.COMPLETED,
            progress=100,
            current_stage="Completed",
            language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            requested_page_numbers_json=[1, 2],
            processed_page_numbers_json=[1, 2],
            failed_page_numbers_json=[],
            requested_by=requested_by,
            requested_at=created_at,
            started_at=created_at,
            completed_at=created_at + timedelta(seconds=2),
            maximum_attempts=2,
            provider="paddleocr",
            provider_version="3.7.0",
            result_summary_json={
                "provider": "paddleocr",
                **({"reOcrReason": reason} if reason is not None else {}),
            },
        )
        session.add(job)
        await session.flush()

        all_blocks = [
            block
            for page_number in (1, 2)
            for block in _page_blocks(page_number, variant)
        ]
        confidences = [confidence for _, confidence, _ in all_blocks]
        total_characters = sum(len(text) for text, _, _ in all_blocks)
        combined_text = "\n".join(text for text, _, _ in all_blocks)
        run = OCRRun(
            ocr_job_id=job.id,
            document_id=source.document_id,
            document_revision_id=source.revision_id,
            document_file_id=source.file_id,
            source_extraction_run_id=source.extraction_run_id,
            provider="paddleocr",
            provider_version="3.7.0",
            language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
            status=OCRRunStatus.COMPLETED,
            source_sha256_hash=(
                await session.get(DocumentFile, source.file_id)
            ).sha256_hash,
            page_count_requested=2,
            page_count_processed=2,
            page_count_failed=0,
            total_blocks=len(all_blocks),
            total_characters=total_characters,
            average_confidence=sum(confidences) / len(confidences),
            minimum_confidence=min(confidences),
            maximum_confidence=max(confidences),
            render_dpi=300,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            content_hash=hashlib.sha256(combined_text.encode()).hexdigest(),
            warnings_json=["OCR_LOW_CONFIDENCE"],
            metadata_json={"processing": "local", "variant": variant},
            started_at=created_at,
            completed_at=created_at + timedelta(seconds=2),
            created_at=created_at,
        )
        session.add(run)
        await session.flush()

        for page_number in (1, 2):
            page_blocks = _page_blocks(page_number, variant)
            raw_text = "\n".join(text for text, _, _ in page_blocks)
            page_confidences = [confidence for _, confidence, _ in page_blocks]
            page = OCRPageResult(
                ocr_run_id=run.id,
                page_number=page_number,
                status=(
                    OCRPageStatus.COMPLETED
                    if page_number == 1
                    else OCRPageStatus.LOW_CONFIDENCE
                ),
                language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
                render_width=2480,
                render_height=3508,
                render_dpi=300,
                rotation_applied=0 if page_number == 1 else 90,
                block_count=len(page_blocks),
                character_count=sum(len(text) for text, _, _ in page_blocks),
                average_confidence=(sum(page_confidences) / len(page_confidences)),
                minimum_confidence=min(page_confidences),
                maximum_confidence=max(page_confidences),
                raw_text=raw_text,
                normalised_text=raw_text,
                content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
                warning_codes_json=([] if page_number == 1 else ["OCR_LOW_CONFIDENCE"]),
                metadata_json={"sourceRotation": 0},
                created_at=created_at,
            )
            session.add(page)
            await session.flush()
            for block_order, (text, confidence, orientation) in enumerate(page_blocks):
                x = float(20 + (block_order * 120))
                session.add(
                    OCRBlock(
                        ocr_run_id=run.id,
                        ocr_page_result_id=page.id,
                        block_order=block_order,
                        text=text,
                        normalised_text=text,
                        confidence=confidence,
                        polygon_json=[
                            [x, 20.0],
                            [x + 100.0, 20.0],
                            [x + 100.0, 50.0],
                            [x, 50.0],
                        ],
                        bbox_json={
                            "x": x,
                            "y": 20.0,
                            "width": 100.0,
                            "height": 30.0,
                        },
                        provider_model="phase7-api-model",
                        recognition_profile=(
                            OCRLanguageProfile.AUTO_MULTILINGUAL.value
                        ),
                        orientation=orientation,
                        metadata_json={
                            "provider": "paddleocr",
                            "processing": "local",
                        },
                        character_count=len(text),
                        created_at=created_at,
                    )
                )

        document_file = await session.get(DocumentFile, source.file_id)
        assert document_file is not None
        document_file.latest_ocr_run_id = run.id
        await session.commit()
        return PersistedOCR(job_id=job.id, run_id=run.id)


async def _disable_ocr_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def do_not_dispatch(
        service: OCRJobService,
        job: OCRJob,
    ) -> None:
        job.worker_reference = "phase7-api-test-task"
        await service.session.commit()

    monkeypatch.setattr(OCRJobService, "_dispatch", do_not_dispatch)


@pytest.mark.asyncio
async def test_ocr_jobs_api_start_list_get_cancel_permissions_and_scope(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    own_department = await _seed_department(
        session_factory,
        code="O71",
    )
    other_department = await _seed_department(
        session_factory,
        code="O72",
    )
    controller = await create_user(
        name="OCR Controller",
        email="ocr.controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=own_department.id,
    )
    department_user = await create_user(
        name="OCR Department User",
        email="ocr.department@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=own_department.id,
    )
    viewer = await create_user(
        name="OCR Viewer",
        email="ocr.viewer@example.com",
        role=UserRole.VIEWER,
        department_id=own_department.id,
    )
    outsider = await create_user(
        name="OCR Outsider",
        email="ocr.outsider@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=other_department.id,
    )
    own_source = await _seed_ocr_source(
        session_factory,
        department=own_department,
        uploaded_by=controller.id,
        number=711,
    )
    other_source = await _seed_ocr_source(
        session_factory,
        department=other_department,
        uploaded_by=controller.id,
        number=712,
    )
    await _disable_ocr_dispatch(monkeypatch)

    department_headers = _headers(department_user, token_service)
    queued = await api_client.post(
        "/api/v1/ocr/jobs",
        headers=department_headers,
        json={
            "documentFileId": str(own_source.file_id),
            "extractionRunId": str(own_source.extraction_run_id),
            "languageProfile": "LATIN",
            "pageNumbers": [1],
            "preprocessingProfile": "AGGRESSIVE",
            "force": False,
        },
    )
    assert queued.status_code == 202, queued.text
    queued_data = queued.json()["data"]
    assert queued_data == {
        "jobId": queued_data["jobId"],
        "status": "QUEUED",
        "progress": 0,
        "pageNumbers": [1],
        "documentFileId": str(own_source.file_id),
        "runId": None,
    }
    job_id = queued_data["jobId"]

    duplicate = await api_client.post(
        "/api/v1/ocr/jobs",
        headers=department_headers,
        json={
            "documentFileId": str(own_source.file_id),
            "extractionRunId": str(own_source.extraction_run_id),
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["errors"][0]["field"] == "documentFileId"
    assert duplicate.json()["errors"][0]["code"] == "OCR_ACTIVE_JOB_EXISTS"

    duplicate_pages = await api_client.post(
        "/api/v1/ocr/jobs",
        headers=department_headers,
        json={
            "documentFileId": str(other_source.file_id),
            "extractionRunId": str(other_source.extraction_run_id),
            "pageNumbers": [1, 1],
        },
    )
    assert duplicate_pages.status_code == 422

    outside_scope = await api_client.post(
        "/api/v1/ocr/jobs",
        headers=department_headers,
        json={
            "documentFileId": str(other_source.file_id),
            "extractionRunId": str(other_source.extraction_run_id),
        },
    )
    assert outside_scope.status_code == 403

    viewer_cannot_start = await api_client.post(
        "/api/v1/ocr/jobs",
        headers=_headers(viewer, token_service),
        json={
            "documentFileId": str(own_source.file_id),
            "extractionRunId": str(own_source.extraction_run_id),
        },
    )
    assert viewer_cannot_start.status_code == 403

    detail = await api_client.get(
        f"/api/v1/ocr/jobs/{job_id}",
        headers=department_headers,
    )
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["jobType"] == "INITIAL_OCR"
    assert detail_data["languageProfile"] == "LATIN"
    assert detail_data["preprocessingProfile"] == "AGGRESSIVE"
    assert detail_data["pageNumbers"] == [1]
    assert detail_data["file"]["id"] == str(own_source.file_id)
    assert detail_data["requestedBy"]["id"] == str(department_user.id)
    assert detail_data["provider"] == "paddleocr"

    viewer_detail = await api_client.get(
        f"/api/v1/ocr/jobs/{job_id}",
        headers=_headers(viewer, token_service),
    )
    assert viewer_detail.status_code == 200, viewer_detail.text

    controller_list = await api_client.get(
        "/api/v1/ocr/jobs",
        headers=_headers(controller, token_service),
        params={
            "search": own_source.document_code,
            "departmentId": str(own_department.id),
            "documentFileId": str(own_source.file_id),
            "status": "QUEUED",
            "languageProfile": "LATIN",
            "requestedBy": str(department_user.id),
            "page": 1,
            "pageSize": 10,
            "sortBy": "progress",
            "sortOrder": "asc",
        },
    )
    assert controller_list.status_code == 200, controller_list.text
    listed = controller_list.json()["data"]
    assert listed["totalItems"] == 1
    assert listed["totalPages"] == 1
    assert listed["items"][0]["id"] == job_id

    viewer_list = await api_client.get(
        "/api/v1/ocr/jobs",
        headers=_headers(viewer, token_service),
    )
    assert viewer_list.status_code == 200, viewer_list.text
    assert viewer_list.json()["data"]["totalItems"] == 1

    outsider_detail = await api_client.get(
        f"/api/v1/ocr/jobs/{job_id}",
        headers=_headers(outsider, token_service),
    )
    assert outsider_detail.status_code == 404
    outsider_list = await api_client.get(
        "/api/v1/ocr/jobs",
        headers=_headers(outsider, token_service),
    )
    assert outsider_list.status_code == 200
    assert outsider_list.json()["data"]["totalItems"] == 0

    department_cannot_cancel = await api_client.post(
        f"/api/v1/ocr/jobs/{job_id}/cancel",
        headers=department_headers,
    )
    assert department_cannot_cancel.status_code == 403

    cancelled = await api_client.post(
        f"/api/v1/ocr/jobs/{job_id}/cancel",
        headers=_headers(controller, token_service),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "CANCEL_REQUESTED"
    assert cancelled.json()["data"]["currentStage"] == ("Cancellation requested")

    cancelled_list = await api_client.get(
        "/api/v1/ocr/jobs",
        headers=_headers(controller, token_service),
        params={"status": "CANCEL_REQUESTED"},
    )
    assert cancelled_list.status_code == 200
    assert cancelled_list.json()["data"]["items"][0]["id"] == job_id

    async with session_factory() as session:
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "OCRJob")
            )
        )
    assert {
        AuditAction.QUEUE_OCR,
        AuditAction.CANCEL_OCR,
    }.issubset(actions)


@pytest.mark.asyncio
async def test_ocr_result_pages_blocks_and_json_txt_exports(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    department = await _seed_department(session_factory, code="O73")
    other_department = await _seed_department(
        session_factory,
        code="O74",
    )
    controller = await create_user(
        name="OCR Result Controller",
        email="ocr.result.controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department.id,
    )
    viewer = await create_user(
        name="OCR Result Viewer",
        email="ocr.result.viewer@example.com",
        role=UserRole.VIEWER,
        department_id=department.id,
    )
    outsider = await create_user(
        name="OCR Result Outsider",
        email="ocr.result.outsider@example.com",
        role=UserRole.VIEWER,
        department_id=other_department.id,
    )
    source = await _seed_ocr_source(
        session_factory,
        department=department,
        uploaded_by=controller.id,
        number=731,
    )
    result = await _seed_completed_ocr(
        session_factory,
        source=source,
        requested_by=controller.id,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
        variant="v1",
    )
    headers = _headers(viewer, token_service)

    run_response = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}",
        headers=headers,
    )
    assert run_response.status_code == 200, run_response.text
    run_data = run_response.json()["data"]
    assert run_data["runId"] == str(result.run_id)
    assert run_data["ocrJobId"] == str(result.job_id)
    assert run_data["status"] == "COMPLETED"
    assert run_data["pageCountRequested"] == 2
    assert run_data["pageCountProcessed"] == 2
    assert run_data["totalBlocks"] == 3
    assert run_data["lowConfidenceBlocks"] == 1
    assert run_data["isLatest"] is True
    assert run_data["provider"] == "paddleocr"
    assert run_data["metadata"]["processing"] == "local"
    assert "storageKey" not in run_response.text

    pages = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/pages",
        headers=headers,
        params={"page": 1, "pageSize": 500},
    )
    assert pages.status_code == 200, pages.text
    pages_data = pages.json()["data"]
    assert pages_data["totalItems"] == 2
    assert pages_data["totalPages"] == 1
    assert pages_data["items"][0]["pageNumber"] == 1

    low_confidence_pages = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/pages",
        headers=headers,
        params={"status": "LOW_CONFIDENCE"},
    )
    assert low_confidence_pages.status_code == 200
    low_page = low_confidence_pages.json()["data"]["items"][0]
    assert low_page["pageNumber"] == 2
    assert low_page["rotationApplied"] == 90
    assert low_page["warningCodes"] == ["OCR_LOW_CONFIDENCE"]

    page_detail = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/pages/1",
        headers=headers,
    )
    assert page_detail.status_code == 200, page_detail.text
    page_data = page_detail.json()["data"]
    assert page_data["page"]["pageNumber"] == 1
    assert len(page_data["blocks"]) == 2
    assert page_data["blocks"][0]["bbox"] == {
        "x": 20.0,
        "y": 20.0,
        "width": 100.0,
        "height": 30.0,
    }
    assert page_data["blocks"][0]["providerModel"] == ("phase7-api-model")

    missing_page = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/pages/99",
        headers=headers,
    )
    assert missing_page.status_code == 404

    blocks = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/blocks",
        headers=headers,
        params={
            "pageNumber": 1,
            "minimumConfidence": 0.4,
            "maximumConfidence": 0.5,
            "search": "manual review",
            "page": 1,
            "pageSize": 10,
        },
    )
    assert blocks.status_code == 200, blocks.text
    blocks_data = blocks.json()["data"]
    assert blocks_data["totalItems"] == 1
    assert blocks_data["items"][0]["confidence"] == pytest.approx(0.45)
    assert blocks_data["items"][0]["pageNumber"] == 1
    assert blocks_data["items"][0]["text"].startswith("Manual review")

    invalid_confidence = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/blocks",
        headers=headers,
        params={
            "minimumConfidence": 0.9,
            "maximumConfidence": 0.2,
        },
    )
    assert invalid_confidence.status_code == 400
    assert invalid_confidence.json()["errors"][0]["field"] == ("minimumConfidence")

    json_export = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/export",
        headers=headers,
        params={"format": "json"},
    )
    assert json_export.status_code == 200, json_export.text
    assert json_export.headers["cache-control"] == "private, no-store"
    assert json_export.headers["x-content-type-options"] == "nosniff"
    assert json_export.headers["content-security-policy"] == ("default-src 'none'")
    assert json_export.headers["content-disposition"].endswith(
        f'filename="ocr-{result.run_id}.json"'
    )
    export_payload = json_export.json()
    assert export_payload["run"]["runId"] == str(result.run_id)
    assert len(export_payload["pages"]) == 2
    assert export_payload["pages"][0]["blocks"][1]["confidence"] == (
        pytest.approx(0.45)
    )
    assert "storageKey" not in json_export.text

    text_export = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/export",
        headers=headers,
        params={"format": "txt"},
    )
    assert text_export.status_code == 200, text_export.text
    assert "[OCR PAGE 1]" in text_export.text
    assert "Kebijakan pengendalian dokumen v1" in text_export.text
    assert "[OCR PAGE 2]" in text_export.text
    assert "文件控制程序 v1" in text_export.text

    invalid_export = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/export",
        headers=headers,
        params={"format": "pdf"},
    )
    assert invalid_export.status_code == 422

    outsider_headers = _headers(outsider, token_service)
    outside_run = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}",
        headers=outsider_headers,
    )
    assert outside_run.status_code == 404
    outside_export = await api_client.get(
        f"/api/v1/ocr/runs/{result.run_id}/export",
        headers=outsider_headers,
    )
    assert outside_export.status_code == 404

    async with session_factory() as session:
        export_actions = list(
            await session.scalars(
                select(AuditLog.action).where(
                    AuditLog.action == AuditAction.EXPORT_OCR_RESULT
                )
            )
        )
    assert len(export_actions) == 2


@pytest.mark.asyncio
async def test_ocr_latest_history_reocr_and_history_permissions(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    department = await _seed_department(session_factory, code="O75")
    other_department = await _seed_department(
        session_factory,
        code="O76",
    )
    controller = await create_user(
        name="OCR History Controller",
        email="ocr.history.controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department.id,
    )
    reviewer = await create_user(
        name="OCR History Reviewer",
        email="ocr.history.reviewer@example.com",
        role=UserRole.REVIEWER,
        department_id=department.id,
    )
    department_user = await create_user(
        name="OCR History Department User",
        email="ocr.history.department@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=department.id,
    )
    viewer = await create_user(
        name="OCR History Viewer",
        email="ocr.history.viewer@example.com",
        role=UserRole.VIEWER,
        department_id=department.id,
    )
    outsider = await create_user(
        name="OCR History Outsider",
        email="ocr.history.outsider@example.com",
        role=UserRole.REVIEWER,
        department_id=other_department.id,
    )
    source = await _seed_ocr_source(
        session_factory,
        department=department,
        uploaded_by=controller.id,
        number=751,
    )
    now = datetime.now(UTC)
    first = await _seed_completed_ocr(
        session_factory,
        source=source,
        requested_by=controller.id,
        created_at=now - timedelta(hours=2),
        variant="initial",
    )
    second = await _seed_completed_ocr(
        session_factory,
        source=source,
        requested_by=controller.id,
        created_at=now - timedelta(hours=1),
        variant="reocr",
        job_type=OCRJobType.RE_OCR,
        reason="Improve Chinese recognition.",
    )
    controller_headers = _headers(controller, token_service)

    latest = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr",
        headers=controller_headers,
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["data"]["runId"] == str(second.run_id)
    assert latest.json()["data"]["isLatest"] is True

    history = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr-history",
        headers=_headers(reviewer, token_service),
        params={"page": 1, "pageSize": 1},
    )
    assert history.status_code == 200, history.text
    history_data = history.json()["data"]
    assert history_data["totalItems"] == 2
    assert history_data["totalPages"] == 2
    assert history_data["items"][0]["id"] == str(second.run_id)
    assert history_data["items"][0]["isLatest"] is True
    assert history_data["items"][0]["reOcrReason"] == ("Improve Chinese recognition.")
    assert history_data["items"][0]["provider"] == "paddleocr"

    history_page_two = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr-history",
        headers=_headers(department_user, token_service),
        params={"page": 2, "pageSize": 1},
    )
    assert history_page_two.status_code == 200
    old_history_item = history_page_two.json()["data"]["items"][0]
    assert old_history_item["id"] == str(first.run_id)
    assert old_history_item["isLatest"] is False

    reviewer_old_run = await api_client.get(
        f"/api/v1/ocr/runs/{first.run_id}",
        headers=_headers(reviewer, token_service),
    )
    assert reviewer_old_run.status_code == 200
    assert reviewer_old_run.json()["data"]["isLatest"] is False

    viewer_old_run = await api_client.get(
        f"/api/v1/ocr/runs/{first.run_id}",
        headers=_headers(viewer, token_service),
    )
    assert viewer_old_run.status_code == 404
    viewer_latest_run = await api_client.get(
        f"/api/v1/ocr/runs/{second.run_id}",
        headers=_headers(viewer, token_service),
    )
    assert viewer_latest_run.status_code == 200
    viewer_history = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr-history",
        headers=_headers(viewer, token_service),
    )
    assert viewer_history.status_code == 403

    outside_latest = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr",
        headers=_headers(outsider, token_service),
    )
    assert outside_latest.status_code == 404
    outside_history = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr-history",
        headers=_headers(outsider, token_service),
    )
    assert outside_history.status_code == 404

    await _disable_ocr_dispatch(monkeypatch)
    blank_reason = await api_client.post(
        f"/api/v1/ocr/runs/{second.run_id}/reocr",
        headers=controller_headers,
        json={"reason": "   "},
    )
    assert blank_reason.status_code == 422

    department_cannot_reocr = await api_client.post(
        f"/api/v1/ocr/runs/{second.run_id}/reocr",
        headers=_headers(department_user, token_service),
        json={"reason": "Retry with a different profile."},
    )
    assert department_cannot_reocr.status_code == 403

    reocr = await api_client.post(
        f"/api/v1/ocr/runs/{second.run_id}/reocr",
        headers=controller_headers,
        json={
            "reason": "Retry page 2 with the Chinese profile.",
            "pageNumbers": [2],
            "languageProfile": "CHINESE_SIMPLIFIED",
            "preprocessingProfile": "AGGRESSIVE",
        },
    )
    assert reocr.status_code == 202, reocr.text
    reocr_data = reocr.json()["data"]
    assert reocr_data["status"] == "QUEUED"
    assert reocr_data["pageNumbers"] == [2]
    assert reocr_data["documentFileId"] == str(source.file_id)

    reocr_detail = await api_client.get(
        f"/api/v1/ocr/jobs/{reocr_data['jobId']}",
        headers=controller_headers,
    )
    assert reocr_detail.status_code == 200, reocr_detail.text
    detail_data = reocr_detail.json()["data"]
    assert detail_data["jobType"] == "RE_OCR"
    assert detail_data["languageProfile"] == "CHINESE_SIMPLIFIED"
    assert detail_data["preprocessingProfile"] == "AGGRESSIVE"
    assert detail_data["resultSummary"]["reOcrReason"] == (
        "Retry page 2 with the Chinese profile."
    )
    assert detail_data["resultSummary"]["sourceOcrRunId"] == str(second.run_id)

    latest_after_queue = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr",
        headers=controller_headers,
    )
    assert latest_after_queue.status_code == 200
    assert latest_after_queue.json()["data"]["runId"] == str(second.run_id)
    history_after_queue = await api_client.get(
        f"/api/v1/document-files/{source.file_id}/ocr-history",
        headers=controller_headers,
    )
    assert history_after_queue.status_code == 200
    assert history_after_queue.json()["data"]["totalItems"] == 2

    async with session_factory() as session:
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "OCRJob")
            )
        )
    assert AuditAction.REOCR_DOCUMENT in actions
