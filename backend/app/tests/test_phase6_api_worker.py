"""Phase 6 extraction API, worker orchestration, and export integration tests."""

from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pymupdf
import pytest
from celery.exceptions import SoftTimeLimitExceeded
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction, UserRole
from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.extraction_job import (
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import ExtractionRun
from app.services.auth.token_service import TokenService
from app.services.extraction.extraction_service import (
    ExtractionService,
    TransientExtractionWorkerError,
)
from app.services.storage.base_storage import BaseStorage, StorageSaveResult
from app.workers import extraction_tasks
from app.workers.extraction_tasks import process_extraction_job
from app.workers.runtime import close_worker_runtime, run_async

TestSessionFactory = async_sessionmaker[AsyncSession]


class MemoryStorage(BaseStorage):
    """Minimal private storage double used only by worker integration tests."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    async def save(
        self,
        source: Any,
        storage_key: str,
    ) -> StorageSaveResult:
        value = source.read()
        self.objects[storage_key] = value
        return {
            "storage_key": storage_key,
            "storage_provider": "memory",
            "size": len(value),
        }

    async def open(self, storage_key: str) -> BytesIO:
        if storage_key not in self.objects:
            raise FileNotFoundError
        return BytesIO(self.objects[storage_key])

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.objects

    async def delete(self, storage_key: str) -> None:
        self.objects.pop(storage_key, None)

    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        self.objects[destination_key] = self.objects.pop(source_key)

    async def get_size(self, storage_key: str) -> int:
        return len(self.objects[storage_key])


def _pdf_bytes(text: str = "Document control procedure selectable text") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


async def _seed_department(
    session_factory: TestSessionFactory,
    *,
    code: str,
) -> Department:
    async with session_factory() as session:
        department = Department(code=code, name=f"{code} Department")
        session.add(department)
        await session.commit()
        await session.refresh(department)
        return department


async def _seed_document_file(
    session_factory: TestSessionFactory,
    *,
    department: Department,
    uploaded_by: Any,
    content: bytes,
    number: str = "006",
) -> DocumentFile:
    async with session_factory() as session:
        document_type = DocumentType(
            code=f"S{number}",
            name=f"Procedure {number}",
            requires_section=False,
        )
        document_status = DocumentStatus(
            code=f"D{number}",
            name=f"Draft {number}",
            is_initial=False,
            display_order=int(number),
        )
        session.add_all((document_type, document_status))
        await session.flush()
        document = Document(
            company_code="MTI",
            department_id=department.id,
            document_type_id=document_type.id,
            document_number=number,
            base_document_code=f"MTI-{department.code}-SOP-{number}",
            title=f"Phase 6 Procedure {number}",
        )
        revision = DocumentRevision(
            document=document,
            revision_code="Rev.000",
            revision_number=0,
            full_document_code=(
                f"MTI-{department.code}-SOP-{number}_Rev.000"
            ),
            document_status_id=document_status.id,
            is_current=True,
        )
        document.current_revision = revision
        source_hash = hashlib.sha256(content).hexdigest()
        document_file = DocumentFile(
            document=document,
            revision=revision,
            original_filename=f"procedure-{number}.pdf",
            sanitized_filename=f"procedure-{number}.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size=len(content),
            sha256_hash=source_hash,
            storage_key=f"documents/originals/tests/{number}.pdf",
            storage_provider="local",
            file_status=DocumentFileStatus.AVAILABLE,
            is_primary=True,
            is_current=True,
            uploaded_by=uploaded_by.id,
        )
        session.add(document_file)
        await session.commit()
        await session.refresh(document_file)
        return document_file


def _headers(user: Any, token_service: TokenService) -> dict[str, str]:
    token = token_service.create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_extraction_api_queue_duplicate_get_list_cancel_and_scope(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    own_department = await _seed_department(session_factory, code="P61")
    other_department = await _seed_department(session_factory, code="P62")
    controller = await create_user(
        email="phase6-controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=own_department.id,
    )
    department_user = await create_user(
        email="phase6-department@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=own_department.id,
    )
    own_file = await _seed_document_file(
        session_factory,
        department=own_department,
        uploaded_by=controller,
        content=_pdf_bytes(),
        number="061",
    )
    other_file = await _seed_document_file(
        session_factory,
        department=other_department,
        uploaded_by=controller,
        content=_pdf_bytes("Other department controlled procedure text"),
        number="062",
    )
    monkeypatch.setattr(
        process_extraction_job,
        "apply_async",
        lambda **_: SimpleNamespace(id="generated-celery-task"),
    )
    controller_headers = _headers(controller, token_service)

    queued = await api_client.post(
        "/api/v1/extractions",
        headers=controller_headers,
        json={"documentFileId": str(own_file.id), "force": False},
    )
    assert queued.status_code == 202, queued.text
    queued_data = queued.json()["data"]
    assert queued_data["status"] == "QUEUED"
    assert queued_data["documentFileId"] == str(own_file.id)
    job_id = queued_data["jobId"]

    duplicate = await api_client.post(
        "/api/v1/extractions",
        headers=controller_headers,
        json={"documentFileId": str(own_file.id), "force": False},
    )
    assert duplicate.status_code == 409

    detail = await api_client.get(
        f"/api/v1/extractions/{job_id}",
        headers=controller_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["file"]["id"] == str(own_file.id)
    assert detail.json()["data"]["maximumAttempts"] == 3

    listed = await api_client.get(
        "/api/v1/extractions",
        headers=controller_headers,
        params={
            "status": "QUEUED",
            "extractorType": "PDF",
            "page": 1,
            "pageSize": 10,
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["totalItems"] == 1

    outside_scope = await api_client.post(
        "/api/v1/extractions",
        headers=_headers(department_user, token_service),
        json={"documentFileId": str(other_file.id), "force": False},
    )
    assert outside_scope.status_code == 403

    cancelled = await api_client.post(
        f"/api/v1/extractions/{job_id}/cancel",
        headers=controller_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "CANCEL_REQUESTED"

    async with session_factory() as session:
        actions = set((await session.scalars(select(AuditLog.action))).all())
    assert AuditAction.QUEUE_DOCUMENT_EXTRACTION in actions
    assert AuditAction.CANCEL_DOCUMENT_EXTRACTION in actions


@pytest.mark.asyncio
async def test_worker_persists_content_and_result_apis_search_export_history(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    department = await _seed_department(session_factory, code="P63")
    controller = await create_user(
        email="phase6-worker@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department.id,
    )
    source = _pdf_bytes(
        "Document control procedure has searchable selectable text"
    )
    document_file = await _seed_document_file(
        session_factory,
        department=department,
        uploaded_by=controller,
        content=source,
        number="063",
    )
    async with session_factory() as session:
        job = ExtractionJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.INITIAL_EXTRACTION,
            status=ExtractionJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            requested_by=controller.id,
            maximum_attempts=3,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    status = await ExtractionService(
        get_settings(),
        session_factory=session_factory,
        storage=MemoryStorage({document_file.storage_key: source}),
    ).process_job(
        job_id,
        worker_reference="test-worker",
    )
    assert status is ExtractionJobStatus.COMPLETED

    async with session_factory() as session:
        run = await session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.extraction_job_id == job_id
            )
        )
        assert run is not None
        run_id = run.id

    headers = _headers(controller, token_service)
    latest = await api_client.get(
        f"/api/v1/document-files/{document_file.id}/extraction",
        headers=headers,
    )
    assert latest.status_code == 200, latest.text
    latest_data = latest.json()["data"]
    assert latest_data["runId"] == str(run_id)
    assert latest_data["totalPages"] == 1
    assert latest_data["isLatest"] is True

    containers = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/containers",
        headers=headers,
        params={"page": 1, "pageSize": 100},
    )
    assert containers.status_code == 200, containers.text
    assert containers.json()["data"]["items"][0]["containerType"] == "PDF_PAGE"

    blocks = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/blocks",
        headers=headers,
        params={"page": 1, "pageSize": 100},
    )
    assert blocks.status_code == 200, blocks.text
    assert blocks.json()["data"]["totalItems"] >= 1
    assert blocks.json()["data"]["items"][0]["location"]["bbox"]

    search = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/search",
        headers=headers,
        params={"q": "searchable selectable"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["data"]["totalMatches"] == 1
    search_item = search.json()["data"]["items"][0]
    assert search_item["blockOrder"] == 1
    assert search_item["containerIndex"] == 1
    assert "<" not in search_item["snippet"]

    history = await api_client.get(
        f"/api/v1/document-files/{document_file.id}/extraction-history",
        headers=headers,
        params={"page": 1, "pageSize": 20},
    )
    assert history.status_code == 200, history.text
    assert history.json()["data"]["totalItems"] == 1
    assert history.json()["data"]["items"][0]["isLatest"] is True

    exported_json = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/export",
        headers=headers,
        params={"format": "json"},
    )
    assert exported_json.status_code == 200, exported_json.text
    export_payload = exported_json.json()
    assert export_payload["run"]["runId"] == str(run_id)
    assert export_payload["blocks"]
    assert "storageKey" not in exported_json.text

    exported_text = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/export",
        headers=headers,
        params={"format": "txt"},
    )
    assert exported_text.status_code == 200
    assert "[PAGE 1]" in exported_text.text
    assert "Document control procedure" in exported_text.text

    reused = await api_client.post(
        "/api/v1/extractions",
        headers=headers,
        json={"documentFileId": str(document_file.id), "force": False},
    )
    assert reused.status_code == 202, reused.text
    assert reused.json()["data"]["reusedExistingResult"] is True
    assert reused.json()["data"]["runId"] == str(run_id)

    invalid_reason = await api_client.post(
        f"/api/v1/document-files/{document_file.id}/reextract",
        headers=headers,
        json={"reason": "  "},
    )
    assert invalid_reason.status_code == 422

    monkeypatch.setattr(
        process_extraction_job,
        "apply_async",
        lambda **_: SimpleNamespace(id="generated-reextraction-task"),
    )
    reextract = await api_client.post(
        f"/api/v1/document-files/{document_file.id}/reextract",
        headers=headers,
        json={"reason": "Extractor configuration updated."},
    )
    assert reextract.status_code == 202, reextract.text
    assert reextract.json()["data"]["status"] == "QUEUED"

    async with session_factory() as session:
        actions = set((await session.scalars(select(AuditLog.action))).all())
    assert AuditAction.COMPLETE_DOCUMENT_EXTRACTION in actions
    assert AuditAction.EXPORT_EXTRACTED_CONTENT in actions


@pytest.mark.asyncio
async def test_worker_marks_controlled_failure_and_honours_prestart_cancel(
    create_user: Any,
    session_factory: TestSessionFactory,
) -> None:
    department = await _seed_department(session_factory, code="P64")
    controller = await create_user(
        email="phase6-failure@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department.id,
    )
    corrupt = b"%PDF-generated-corrupt"
    document_file = await _seed_document_file(
        session_factory,
        department=department,
        uploaded_by=controller,
        content=corrupt,
        number="064",
    )
    async with session_factory() as session:
        failed_job = ExtractionJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.INITIAL_EXTRACTION,
            status=ExtractionJobStatus.QUEUED,
            progress=0,
            requested_by=controller.id,
        )
        session.add(failed_job)
        await session.commit()
        failed_job_id = failed_job.id

    service = ExtractionService(
        get_settings(),
        session_factory=session_factory,
        storage=MemoryStorage({document_file.storage_key: corrupt}),
    )
    failed_status = await service.process_job(failed_job_id)
    assert failed_status is ExtractionJobStatus.FAILED

    async with session_factory() as session:
        failed = await session.get(ExtractionJob, failed_job_id)
        assert failed is not None
        assert failed.error_code == "PDF_CORRUPT"
        assert "traceback" not in (failed.error_message or "").lower()
        failed.status = ExtractionJobStatus.CANCEL_REQUESTED
        failed.error_code = None
        failed.error_message = None
        await session.commit()

    cancelled_status = await service.process_job(failed_job_id)
    assert cancelled_status is ExtractionJobStatus.CANCELLED
    async with session_factory() as session:
        cancelled = await session.get(ExtractionJob, failed_job_id)
        assert cancelled is not None
        assert cancelled.status is ExtractionJobStatus.CANCELLED


def test_celery_task_marks_soft_timeout_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class TimeoutService:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def process_job(
            self,
            *_: object,
            **__: object,
        ) -> ExtractionJobStatus:
            raise SoftTimeLimitExceeded

        async def fail_job(
            self,
            _job_id: object,
            **kwargs: object,
        ) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(extraction_tasks, "ExtractionService", TimeoutService)
    job_id = str(uuid4())
    try:
        result = process_extraction_job.run(job_id)
    finally:
        close_worker_runtime()

    assert result == {"jobId": job_id, "status": "FAILED"}
    assert calls[0]["error_code"] == "EXTRACTION_TIMEOUT"


def test_celery_task_retries_only_transient_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TransientService:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def process_job(
            self,
            *_: object,
            **__: object,
        ) -> ExtractionJobStatus:
            raise TransientExtractionWorkerError("temporary")

    class RetryWasRequested(Exception):
        pass

    retry_arguments: dict[str, object] = {}

    def retry(**kwargs: object) -> None:
        retry_arguments.update(kwargs)
        raise RetryWasRequested

    monkeypatch.setattr(
        extraction_tasks,
        "ExtractionService",
        TransientService,
    )
    monkeypatch.setattr(
        process_extraction_job._get_current_object(),
        "retry",
        retry,
    )

    try:
        with pytest.raises(RetryWasRequested):
            process_extraction_job.run(str(uuid4()))
    finally:
        close_worker_runtime()
    assert retry_arguments["countdown"] == 2
    assert isinstance(
        retry_arguments["exc"],
        TransientExtractionWorkerError,
    )


def test_worker_runtime_reuses_one_event_loop_per_process() -> None:
    async def loop_identity() -> int:
        return id(asyncio.get_running_loop())

    try:
        assert run_async(loop_identity()) == run_async(loop_identity())
    finally:
        close_worker_runtime()
