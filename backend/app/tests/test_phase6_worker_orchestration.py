"""Focused worker lifecycle tests using private generated source bytes."""

from __future__ import annotations

import hashlib
import inspect
import io
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.authorization import AuditAction
from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.extraction_job import (
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import ExtractionRun
from app.schemas.extraction import (
    ExtractedBlockData,
    ExtractedBlockType,
    ExtractedContainerData,
    ExtractedContainerType,
    ExtractedDocumentData,
)
from app.services.extraction.extraction_service import ExtractionService
from app.services.storage.local_storage import LocalStorage
from app.workers.extraction_tasks import process_extraction_job

SOURCE_BYTES = b"%PDF-1.4\n% generated Phase 6 worker fixture\n%%EOF\n"


def _worker_graph(
    *,
    storage_key: str,
    status: ExtractionJobStatus,
) -> tuple[Document, DocumentRevision, DocumentFile, ExtractionJob]:
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number="064",
        base_document_code=f"MTI-HRM-POL-{uuid4().hex[:8].upper()}",
        title="Worker Lifecycle Policy",
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
        original_filename="worker-source.pdf",
        sanitized_filename="worker-source.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=len(SOURCE_BYTES),
        sha256_hash=hashlib.sha256(SOURCE_BYTES).hexdigest(),
        storage_key=storage_key,
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    job = ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=status,
        progress=0,
    )
    return document, revision, document_file, job


def _result() -> ExtractedDocumentData:
    return ExtractedDocumentData(
        extractor_type="PDF",
        containers=[
            ExtractedContainerData(
                container_type=ExtractedContainerType.PDF_PAGE,
                container_index=1,
                name="Page 1",
                raw_text="Worker extraction",
                normalised_text="Worker extraction",
                character_count=17,
                word_count=2,
                blocks=[
                    ExtractedBlockData(
                        block_type=ExtractedBlockType.TEXT,
                        block_order=1,
                        source_reference="PDF:page=1:block=1",
                        text="Worker extraction",
                        normalised_text="Worker extraction",
                        location={"page": 1},
                        character_count=17,
                        word_count=2,
                    )
                ],
            )
        ],
    )


class _FakeExtractor:
    async def inspect(self, _path) -> dict[str, object]:
        return {"safe": True}

    async def extract(
        self,
        _path,
        context: dict[str, object],
    ) -> ExtractedDocumentData:
        callback = context["progress_callback"]
        progress = callback(50, "Extracting generated page")
        if inspect.isawaitable(progress):
            await progress
        cancellation_checker = context["cancellation_checker"]
        cancelled = cancellation_checker()
        if inspect.isawaitable(cancelled):
            cancelled = await cancelled
        assert cancelled is False
        return _result()


@pytest.mark.asyncio
async def test_worker_processes_job_persists_latest_and_closes_sessions(
    session_factory,
    tmp_path,
    monkeypatch,
) -> None:
    storage = LocalStorage(tmp_path)
    storage_key = "documents/originals/worker/source.pdf"
    await storage.save(io.BytesIO(SOURCE_BYTES), storage_key)
    document, revision, document_file, job = _worker_graph(
        storage_key=storage_key,
        status=ExtractionJobStatus.QUEUED,
    )
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()
        job_id = job.id
        file_id = document_file.id

    monkeypatch.setattr(
        "app.services.extraction.extraction_service.get_extractor",
        lambda _extension: _FakeExtractor(),
    )
    status = await ExtractionService(
        get_settings(),
        session_factory=session_factory,
        storage=storage,
    ).process_job(
        job_id,
        worker_reference="pytest-worker",
        attempt_number=1,
    )

    assert status is ExtractionJobStatus.COMPLETED
    async with session_factory() as session:
        persisted_job = await session.get(ExtractionJob, job_id)
        persisted_file = await session.get(DocumentFile, file_id)
        run = await session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.document_file_id == file_id
            )
        )
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.COMPLETE_DOCUMENT_EXTRACTION
            )
        )
        assert persisted_job is not None
        assert persisted_job.status is ExtractionJobStatus.COMPLETED
        assert persisted_job.progress == 100
        assert persisted_job.worker_reference == "pytest-worker"
        assert persisted_file is not None
        assert run is not None
        assert persisted_file.latest_extraction_run_id == run.id
        assert audit is not None


@pytest.mark.asyncio
async def test_worker_honours_preexisting_cancel_request(
    session_factory,
    tmp_path,
) -> None:
    document, revision, document_file, job = _worker_graph(
        storage_key="documents/originals/worker/missing.pdf",
        status=ExtractionJobStatus.CANCEL_REQUESTED,
    )
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()
        job_id = job.id

    status = await ExtractionService(
        get_settings(),
        session_factory=session_factory,
        storage=LocalStorage(tmp_path),
    ).process_job(job_id)

    assert status is ExtractionJobStatus.CANCELLED
    async with session_factory() as session:
        persisted_job = await session.get(ExtractionJob, job_id)
        assert persisted_job is not None
        assert persisted_job.status is ExtractionJobStatus.CANCELLED
        assert persisted_job.cancelled_at is not None


def test_celery_task_rejects_invalid_job_identifier_without_retry() -> None:
    assert process_extraction_job.run("not-a-uuid") == {
        "jobId": "not-a-uuid",
        "status": ExtractionJobStatus.FAILED.value,
    }
