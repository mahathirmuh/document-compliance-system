"""Integrated native/OCR extracted-content viewer contract tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.core.authorization import UserRole
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
    LanguageBlockResult,
    LanguageCode,
    LanguageEligibilityStatus,
    LanguageSourceType,
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
from app.services.auth.token_service import TokenService


async def _seed_merged_view(
    session_factory,
    *,
    department_id: UUID,
) -> tuple[UUID, UUID]:
    long_native_text = "Native selectable policy text applies to all teams. " * 2
    short_native_text = "Note"
    chinese_ocr_text = "文件控制程序适用于所有部门。"
    document = Document(
        company_code="MTI",
        department_id=department_id,
        document_type_id=uuid4(),
        document_number="077",
        base_document_code="MTI-QMS-POL-077",
        title="Merged Viewer Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-QMS-POL-077_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="MTI-QMS-POL-077_Rev.000.pdf",
        sanitized_filename="MTI-QMS-POL-077_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=4096,
        sha256_hash="a" * 64,
        storage_key="documents/originals/merged-viewer.pdf",
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
        source_sha256_hash=document_file.sha256_hash,
        source_file_size=document_file.file_size,
        content_hash="b" * 64,
        total_pages=2,
        total_blocks=2,
        total_characters=len(long_native_text) + len(short_native_text),
        total_words=len(long_native_text.split()) + 1,
        has_selectable_text=True,
        requires_ocr=True,
        warnings_json=[],
    )
    first_container = ExtractedContainer(
        extraction_run=extraction_run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=1,
        name="Page 1",
        raw_text=long_native_text,
        normalised_text=long_native_text,
        character_count=len(long_native_text),
        word_count=len(long_native_text.split()),
    )
    second_container = ExtractedContainer(
        extraction_run=extraction_run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=2,
        name="Page 2",
        raw_text=short_native_text,
        normalised_text=short_native_text,
        character_count=len(short_native_text),
        word_count=1,
    )
    first_native = ExtractedBlock(
        extraction_run=extraction_run,
        container=first_container,
        block_type=ExtractedBlockType.TEXT,
        block_order=1,
        source_reference="PDF:page=1:block=1",
        text=long_native_text,
        normalised_text=long_native_text,
        character_count=len(long_native_text),
        word_count=len(long_native_text.split()),
    )
    second_native = ExtractedBlock(
        extraction_run=extraction_run,
        container=second_container,
        block_type=ExtractedBlockType.TEXT,
        block_order=1,
        source_reference="PDF:page=2:block=1",
        text=short_native_text,
        normalised_text=short_native_text,
        character_count=len(short_native_text),
        word_count=1,
    )
    ocr_job = OCRJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        job_type=OCRJobType.INITIAL_OCR,
        status=OCRJobStatus.COMPLETED,
        progress=100,
        language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        maximum_attempts=1,
    )
    ocr_run = OCRRun(
        ocr_job=ocr_job,
        document=document,
        revision=revision,
        document_file=document_file,
        source_extraction_run=extraction_run,
        provider="paddleocr",
        provider_version="3.7.0",
        language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
        status=OCRRunStatus.COMPLETED,
        source_sha256_hash=document_file.sha256_hash,
        page_count_requested=2,
        page_count_processed=2,
        page_count_failed=0,
        total_blocks=3,
        total_characters=64,
        average_confidence=0.84,
        minimum_confidence=0.80,
        maximum_confidence=0.88,
        render_dpi=300,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        content_hash="c" * 64,
        warnings_json=[],
    )
    first_ocr_page = OCRPageResult(
        ocr_run=ocr_run,
        page_number=1,
        status=OCRPageStatus.COMPLETED,
        language_profile=OCRLanguageProfile.LATIN,
        render_width=1200,
        render_height=1600,
        render_dpi=300,
        block_count=1,
        character_count=24,
        average_confidence=0.80,
        raw_text="Suppressed OCR page one",
        normalised_text="Suppressed OCR page one",
        warning_codes_json=[],
    )
    second_ocr_page = OCRPageResult(
        ocr_run=ocr_run,
        page_number=2,
        status=OCRPageStatus.COMPLETED,
        language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
        render_width=1200,
        render_height=1600,
        render_dpi=300,
        block_count=2,
        character_count=len(short_native_text) + len(chinese_ocr_text),
        average_confidence=0.86,
        raw_text=f"{short_native_text}\n{chinese_ocr_text}",
        normalised_text=f"{short_native_text}\n{chinese_ocr_text}",
        warning_codes_json=[],
    )

    def ocr_block(
        page_result: OCRPageResult,
        order: int,
        text: str,
        confidence: float,
    ) -> OCRBlock:
        return OCRBlock(
            ocr_run=ocr_run,
            page_result=page_result,
            block_order=order,
            text=text,
            normalised_text=text,
            confidence=confidence,
            polygon_json=[
                [10.0, 20.0],
                [200.0, 20.0],
                [200.0, 60.0],
                [10.0, 60.0],
            ],
            bbox_json={
                "x": 10.0,
                "y": 20.0,
                "width": 190.0,
                "height": 40.0,
            },
            provider_model="latin-and-chinese-test",
            recognition_profile="AUTO_MULTILINGUAL",
            orientation=0,
            character_count=len(text),
        )

    suppressed_ocr = ocr_block(
        first_ocr_page,
        1,
        "Suppressed OCR page one",
        0.80,
    )
    duplicate_ocr = ocr_block(
        second_ocr_page,
        1,
        short_native_text,
        0.88,
    )
    chinese_ocr = ocr_block(
        second_ocr_page,
        2,
        chinese_ocr_text,
        0.84,
    )
    language_job = LanguageDetectionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        ocr_run_id=ocr_run.id,
        status=LanguageDetectionJobStatus.COMPLETED,
        progress=100,
        source_content_hash="d" * 64,
        maximum_attempts=1,
    )
    language_run = LanguageDetectionRun(
        job=language_job,
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        ocr_run_id=ocr_run.id,
        detector_name="hybrid-unicode-fasttext",
        detector_version="1.0",
        status=LanguageDetectionRunStatus.COMPLETED,
        source_content_hash="d" * 64,
        total_blocks=3,
        eligible_blocks=2,
        detected_blocks=2,
        english_blocks=1,
        chinese_blocks=1,
        total_characters=len(long_native_text) + len(chinese_ocr_text),
        english_characters=len(long_native_text),
        chinese_characters=len(chinese_ocr_text),
        average_confidence=0.94,
        warnings_json=[],
    )

    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                first_container,
                second_container,
                first_native,
                second_native,
                ocr_job,
                ocr_run,
                first_ocr_page,
                second_ocr_page,
                suppressed_ocr,
                duplicate_ocr,
                chinese_ocr,
                language_job,
                language_run,
            ]
        )
        await session.flush()
        session.add_all(
            [
                LanguageBlockResult(
                    language_detection_run_id=language_run.id,
                    extracted_block_id=first_native.id,
                    ocr_block_id=None,
                    container_id=first_container.id,
                    source_type=LanguageSourceType.NATIVE_EXTRACTION,
                    source_reference=first_native.source_reference,
                    language_code=LanguageCode.ENGLISH,
                    primary_language_code=LanguageCode.ENGLISH,
                    confidence=0.96,
                    is_mixed=False,
                    detected_languages_json=[
                        {"languageCode": "en", "score": 0.96}
                    ],
                    script_statistics_json={},
                    eligibility_status=LanguageEligibilityStatus.ELIGIBLE,
                    eligibility_reason=None,
                    character_count=len(long_native_text),
                    latin_character_count=len(long_native_text),
                    han_character_count=0,
                    word_count=len(long_native_text.split()),
                ),
                LanguageBlockResult(
                    language_detection_run_id=language_run.id,
                    extracted_block_id=None,
                    ocr_block_id=chinese_ocr.id,
                    container_id=second_container.id,
                    source_type=LanguageSourceType.OCR,
                    source_reference="OCR:page=2:block=2",
                    language_code=LanguageCode.CHINESE,
                    primary_language_code=LanguageCode.CHINESE,
                    confidence=0.92,
                    is_mixed=False,
                    detected_languages_json=[
                        {"languageCode": "zh", "score": 0.92}
                    ],
                    script_statistics_json={},
                    eligibility_status=LanguageEligibilityStatus.ELIGIBLE,
                    eligibility_reason=None,
                    character_count=len(chinese_ocr_text),
                    latin_character_count=0,
                    han_character_count=len(chinese_ocr_text),
                    word_count=1,
                ),
            ]
        )
        document_file.latest_extraction_run_id = extraction_run.id
        document_file.latest_ocr_run_id = ocr_run.id
        document_file.latest_language_detection_run_id = language_run.id
        await session.commit()
    return extraction_run.id, second_container.id


@pytest.mark.asyncio
async def test_extracted_content_viewer_merges_sources_and_annotations(
    api_client: AsyncClient,
    create_user,
    token_service: TokenService,
    session_factory,
) -> None:
    department_id = uuid4()
    viewer = await create_user(
        email="merged.viewer@example.com",
        role=UserRole.VIEWER,
        department_id=department_id,
    )
    run_id, second_container_id = await _seed_merged_view(
        session_factory,
        department_id=department_id,
    )
    headers = {
        "Authorization": (
            f"Bearer {token_service.create_access_token(viewer)}"
        )
    }

    response = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/blocks",
        headers=headers,
        params={"page": 1, "pageSize": 100},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["totalItems"] == 3
    assert [item["contentSource"] for item in payload["items"]] == [
        "NATIVE",
        "NATIVE",
        "OCR",
    ]

    english = payload["items"][0]
    assert english["languageCode"] == "en"
    assert english["languageConfidence"] == pytest.approx(0.96)
    assert english["ocrConfidence"] is None
    assert english["provenance"]["source"] == "EXTRACTION"
    assert english["provenance"]["extractionRunId"] == str(run_id)
    assert english["provenance"]["languageDetectionRunId"]

    ocr = payload["items"][2]
    assert ocr["languageCode"] == "zh"
    assert ocr["languageConfidence"] == pytest.approx(0.92)
    assert ocr["ocrConfidence"] == pytest.approx(0.84)
    assert ocr["location"]["bbox"]["width"] == pytest.approx(190.0)
    assert ocr["provenance"]["source"] == "OCR"
    assert ocr["provenance"]["ocrBlockId"] == ocr["id"]
    assert ocr["provenance"]["ocrRunId"]
    assert "storageKey" not in response.text

    page_two = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/blocks",
        headers=headers,
        params={
            "containerId": str(second_container_id),
            "page": 1,
            "pageSize": 100,
        },
    )
    assert page_two.status_code == 200
    assert page_two.json()["data"]["totalItems"] == 2

    ocr_only = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/blocks",
        headers=headers,
        params={"contentSource": "OCR"},
    )
    assert ocr_only.status_code == 200
    assert ocr_only.json()["data"]["totalItems"] == 1
    assert ocr_only.json()["data"]["items"][0]["contentSource"] == "OCR"

    chinese_only = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/blocks",
        headers=headers,
        params={"languageCode": "zh"},
    )
    assert chinese_only.status_code == 200
    assert chinese_only.json()["data"]["totalItems"] == 1
    assert chinese_only.json()["data"]["items"][0]["languageCode"] == "zh"
