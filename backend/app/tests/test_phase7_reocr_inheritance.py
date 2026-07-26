"""Targeted re-OCR ancestry and effective-source integration tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
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
from app.schemas.language_internal import LanguageDetectionData
from app.schemas.ocr_internal import (
    OCRBlockData,
    OCRBoundingBox,
)
from app.schemas.ocr_internal import (
    OCRPageResult as OCRPageData,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.extraction.extraction_content_service import (
    ExtractionContentService,
)
from app.services.language.base_language_detector import BaseLanguageDetector
from app.services.language.language_detection_service import (
    LanguageDetectionService,
)
from app.services.ocr.ocr_persistence_service import OCRPersistenceService
from app.services.ocr.ocr_source_chain_service import OCRSourceChainService


class _UnusedDetector(BaseLanguageDetector):
    def detect(self, text: str) -> LanguageDetectionData:
        raise AssertionError(f"Detection was not expected for {text!r}.")

    def get_detector_info(self) -> dict[str, object]:
        return {"name": "unused", "version": "test"}


def _ocr_block_data(text: str) -> OCRBlockData:
    return OCRBlockData(
        text=text,
        normalised_text=text,
        confidence=0.91,
        polygon=[
            [10.0, 10.0],
            [200.0, 10.0],
            [200.0, 60.0],
            [10.0, 60.0],
        ],
        bbox=OCRBoundingBox(
            x=10.0,
            y=10.0,
            width=190.0,
            height=50.0,
        ),
        provider_model="targeted-reocr-test",
        recognition_profile=OCRLanguageProfile.LATIN,
    )


def _stored_ocr_block(
    run: OCRRun,
    page: OCRPageResult,
    *,
    text: str,
) -> OCRBlock:
    return OCRBlock(
        ocr_run=run,
        page_result=page,
        block_order=0,
        text=text,
        normalised_text=text,
        confidence=0.90,
        polygon_json=[
            [10.0, 10.0],
            [200.0, 10.0],
            [200.0, 60.0],
            [10.0, 60.0],
        ],
        bbox_json={
            "x": 10.0,
            "y": 10.0,
            "width": 190.0,
            "height": 50.0,
        },
        provider_model="targeted-reocr-test",
        recognition_profile=OCRLanguageProfile.LATIN.value,
        orientation=0,
        character_count=len(text),
    )


async def _seed_targeted_reocr(
    session_factory,
    *,
    department_id: UUID,
) -> tuple[UUID, UUID, UUID, UUID]:
    parent_page_one_text = "Inherited OCR text from page one."
    parent_page_two_text = "Obsolete OCR text from page two."
    replacement_page_two_text = "Replacement OCR text from page two."
    document = Document(
        company_code="MTI",
        department_id=department_id,
        document_type_id=uuid4(),
        document_number="701",
        base_document_code="MTI-QMS-POL-701",
        title="Targeted Re-OCR Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-QMS-POL-701_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="MTI-QMS-POL-701_Rev.000.pdf",
        sanitized_filename="MTI-QMS-POL-701_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=4096,
        sha256_hash="a" * 64,
        storage_key="documents/originals/tests/targeted-reocr.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    extraction_job = ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=ExtractionJobStatus.PARTIALLY_COMPLETED,
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
        status=ExtractionRunStatus.PARTIALLY_COMPLETED,
        source_sha256_hash=document_file.sha256_hash,
        source_file_size=document_file.file_size,
        content_hash="b" * 64,
        total_pages=2,
        total_blocks=0,
        total_characters=0,
        total_words=0,
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
    parent_job = OCRJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        job_type=OCRJobType.INITIAL_OCR,
        status=OCRJobStatus.COMPLETED,
        progress=100,
        language_profile=OCRLanguageProfile.LATIN,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        requested_page_numbers_json=[1, 2],
        processed_page_numbers_json=[1, 2],
        failed_page_numbers_json=[],
        maximum_attempts=1,
        result_summary_json={},
    )
    parent_run = OCRRun(
        ocr_job=parent_job,
        document=document,
        revision=revision,
        document_file=document_file,
        source_extraction_run=extraction_run,
        provider="paddleocr",
        provider_version="3.7.0",
        language_profile=OCRLanguageProfile.LATIN,
        status=OCRRunStatus.COMPLETED,
        source_sha256_hash=document_file.sha256_hash,
        page_count_requested=2,
        page_count_processed=2,
        page_count_failed=0,
        total_blocks=2,
        total_characters=(len(parent_page_one_text) + len(parent_page_two_text)),
        render_dpi=300,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        content_hash="c" * 64,
        warnings_json=[],
        metadata_json={},
    )
    parent_pages = [
        OCRPageResult(
            ocr_run=parent_run,
            page_number=page_number,
            status=OCRPageStatus.COMPLETED,
            language_profile=OCRLanguageProfile.LATIN,
            render_width=1200,
            render_height=1600,
            render_dpi=300,
            block_count=1,
            character_count=len(text),
            average_confidence=0.90,
            minimum_confidence=0.90,
            maximum_confidence=0.90,
            raw_text=text,
            normalised_text=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            warning_codes_json=[],
        )
        for page_number, text in (
            (1, parent_page_one_text),
            (2, parent_page_two_text),
        )
    ]
    parent_blocks = [
        _stored_ocr_block(parent_run, page, text=text)
        for page, text in zip(
            parent_pages,
            (parent_page_one_text, parent_page_two_text),
            strict=True,
        )
    ]

    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                *containers,
                parent_job,
                parent_run,
                *parent_pages,
                *parent_blocks,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        document_file.latest_ocr_run_id = parent_run.id
        await session.flush()

        replacement_job = OCRJob(
            document=document,
            revision=revision,
            document_file=document_file,
            extraction_run=extraction_run,
            job_type=OCRJobType.RE_OCR,
            status=OCRJobStatus.QUEUED,
            progress=0,
            language_profile=OCRLanguageProfile.LATIN,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            requested_page_numbers_json=[2],
            processed_page_numbers_json=[],
            failed_page_numbers_json=[],
            maximum_attempts=1,
            result_summary_json={
                "sourceOcrRunId": str(parent_run.id),
                "reOcrReason": "Replace only the second page.",
                "pageSelection": {
                    "selectedPageNumbers": [2],
                    "skippedPageNumbers": [1],
                },
            },
        )
        session.add(replacement_job)
        await session.flush()
        persistence = OCRPersistenceService(session)
        replacement_run = await persistence.create_or_get_run(
            job=replacement_job,
            document_file=document_file,
            provider_version="3.7.0",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await persistence.persist_page(
            replacement_run,
            OCRPageData(
                page_number=2,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[_ocr_block_data(replacement_page_two_text)],
            ),
        )
        await persistence.finalize(
            job=replacement_job,
            run=replacement_run,
            completed_at=datetime.now(UTC),
        )
        effective = await OCRSourceChainService(session).resolve(replacement_run)

        assert [page.page_number for page in effective.pages] == [1, 2]
        assert [page.normalised_text for page in effective.pages] == [
            parent_page_one_text,
            replacement_page_two_text,
        ]
        assert effective.block_count == 2
        assert replacement_run.content_hash == effective.content_hash
        assert replacement_job.result_summary_json is not None
        assert replacement_job.result_summary_json["sourceOcrRunId"] == str(
            parent_run.id
        )
        assert replacement_job.result_summary_json["reOcrReason"] == (
            "Replace only the second page."
        )
        assert replacement_run.metadata_json is not None
        assert replacement_run.metadata_json["effectivePageNumbers"] == [1, 2]
        assert replacement_run.metadata_json["effectiveBlockCount"] == 2
        await session.commit()
        return (
            extraction_run.id,
            parent_run.id,
            replacement_run.id,
            document_file.id,
        )


@pytest.mark.asyncio
async def test_targeted_reocr_inherits_unselected_pages_for_view_and_language(
    create_user,
    session_factory,
) -> None:
    department_id = uuid4()
    viewer = await create_user(
        name="Targeted Re-OCR Viewer",
        email="targeted.reocr.viewer@example.com",
        role=UserRole.VIEWER,
        department_id=department_id,
    )
    (
        extraction_run_id,
        parent_run_id,
        replacement_run_id,
        _,
    ) = await _seed_targeted_reocr(
        session_factory,
        department_id=department_id,
    )

    async with session_factory() as session:
        blocks = await ExtractionContentService(
            session,
            get_settings(),
            viewer,
            RequestMetadata(ip_address=None, user_agent="pytest"),
        ).list_blocks(
            extraction_run_id,
            container_id=None,
            block_type=None,
            content_source=None,
            language_code=None,
            search=None,
            page=1,
            page_size=100,
            sort_order="asc",
        )

    assert blocks.total_items == 2
    assert [item.text for item in blocks.items] == [
        "Inherited OCR text from page one.",
        "Replacement OCR text from page two.",
    ]
    assert [item.provenance["ocrRunId"] for item in blocks.items] == [
        str(parent_run_id),
        str(replacement_run_id),
    ]
    assert all(item.text != "Obsolete OCR text from page two." for item in blocks.items)

    language_service = LanguageDetectionService(
        get_settings(),
        session_factory=session_factory,
        detector=_UnusedDetector(),
    )
    sources = await language_service._load_sources(
        extraction_run_id,
        replacement_run_id,
    )
    assert [source.text for source in sources] == [
        "Inherited OCR text from page one.",
        "Replacement OCR text from page two.",
    ]
    assert [source.page_number for source in sources] == [1, 2]
    assert len({source.ocr_block_id for source in sources}) == 2


@pytest.mark.asyncio
async def test_newest_no_text_page_owns_page_without_resurrecting_ancestor(
    session_factory,
) -> None:
    (
        extraction_run_id,
        parent_run_id,
        replacement_run_id,
        document_file_id,
    ) = await _seed_targeted_reocr(
        session_factory,
        department_id=uuid4(),
    )

    async with session_factory() as session:
        document_file = await session.get(DocumentFile, document_file_id)
        replacement_run = await session.get(OCRRun, replacement_run_id)
        extraction_run = await session.get(
            ExtractionRun,
            extraction_run_id,
        )
        assert document_file is not None
        assert replacement_run is not None
        assert extraction_run is not None
        no_text_job = OCRJob(
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            document_file_id=document_file.id,
            extraction_run_id=extraction_run.id,
            job_type=OCRJobType.RE_OCR,
            status=OCRJobStatus.QUEUED,
            progress=0,
            language_profile=OCRLanguageProfile.LATIN,
            preprocessing_profile=OCRPreprocessingProfile.STANDARD,
            requested_page_numbers_json=[2],
            processed_page_numbers_json=[],
            failed_page_numbers_json=[],
            maximum_attempts=1,
            result_summary_json={
                "sourceOcrRunId": str(replacement_run.id),
                "reOcrReason": "Confirm that page two is blank.",
            },
        )
        session.add(no_text_job)
        await session.flush()
        persistence = OCRPersistenceService(session)
        no_text_run = await persistence.create_or_get_run(
            job=no_text_job,
            document_file=document_file,
            provider_version="3.7.0",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await persistence.persist_page(
            no_text_run,
            OCRPageData(
                page_number=2,
                status=OCRPageStatus.NO_TEXT_FOUND,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[],
                warning_codes=["NO_TEXT_FOUND"],
            ),
        )
        await persistence.finalize(
            job=no_text_job,
            run=no_text_run,
            completed_at=datetime.now(UTC),
        )
        effective = await OCRSourceChainService(session).resolve(no_text_run)
        no_text_run_id = no_text_run.id
        await session.commit()

    assert effective.run_ids == (
        no_text_run_id,
        replacement_run_id,
        parent_run_id,
    )
    assert [page.page_number for page in effective.pages] == [1, 2]
    assert [page.normalised_text for page in effective.pages] == [
        "Inherited OCR text from page one.",
        "",
    ]
    assert effective.block_count == 1
    assert [(group.run_id, group.page_numbers) for group in effective.pages_by_run] == [
        (no_text_run_id, (2,)),
        (parent_run_id, (1,)),
    ]
    sources = await LanguageDetectionService(
        get_settings(),
        session_factory=session_factory,
        detector=_UnusedDetector(),
    )._load_sources(
        extraction_run_id,
        no_text_run_id,
    )
    assert [(source.page_number, source.text) for source in sources] == [
        (1, "Inherited OCR text from page one.")
    ]
