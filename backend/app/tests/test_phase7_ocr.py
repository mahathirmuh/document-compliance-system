"""Focused Phase 7 local OCR provider, page, merge, and persistence tests."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pymupdf
import pytest
from sqlalchemy import select

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.database.base import Base
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
from app.models.language_block_result import LanguageBlockResult
from app.models.language_container_summary import LanguageContainerSummary
from app.models.language_detection_job import LanguageDetectionJob
from app.models.language_detection_run import LanguageDetectionRun
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import (
    ACTIVE_OCR_JOB_STATUSES,
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_page_result import OCRPageResult, OCRPageStatus
from app.models.ocr_run import OCRRunStatus
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_job_repository import OCRJobRepository
from app.repositories.ocr_page_result_repository import (
    OCRPageResultRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.ocr import OCRReprocessRequest, OCRStartRequest
from app.schemas.ocr_internal import (
    OCRBlockData,
    OCRBoundingBox,
)
from app.schemas.ocr_internal import (
    OCRPageResult as OCRPageData,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.ocr.base_ocr_provider import (
    BaseOCRProvider,
    OCRProviderUnavailableError,
    OCRResourceLimitError,
)
from app.services.ocr.ocr_job_service import OCRJobService
from app.services.ocr.ocr_merge_service import OCRMergeService
from app.services.ocr.ocr_page_service import OCRPageService
from app.services.ocr.ocr_persistence_service import OCRPersistenceService
from app.services.ocr.ocr_preprocessing_service import (
    OCRPreprocessingService,
)
from app.services.ocr.ocr_render_service import OCRRenderService
from app.services.ocr.ocr_service import OCRService
from app.services.ocr.ocr_temporary_cleanup_service import (
    OCRTemporaryCleanupService,
)
from app.services.ocr.paddle_ocr_provider import PaddleOCRProvider
from app.services.storage.base_storage import BaseStorage, StorageSaveResult
from app.workers.ocr_tasks import process_ocr_job

# Imports above register all cross-vertical Phase 7 table names for SQLite.
_LANGUAGE_MODELS = (
    LanguageDetectionJob,
    LanguageDetectionRun,
    LanguageBlockResult,
    LanguageContainerSummary,
)


def _pdf(path: Path, *, rotation: int = 0) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((30, 50), "Generated OCR test page")
    if rotation:
        page.set_rotation(rotation)
    document.save(path)
    document.close()
    return path


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = pymupdf.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page(width=300, height=200)
        page.insert_text((30, 50), f"Generated OCR page {page_number}")
    payload = document.tobytes()
    document.close()
    return payload


def _block(
    text: str = "Kebijakan dokumen",
    confidence: float = 0.9,
    *,
    profile: OCRLanguageProfile = OCRLanguageProfile.LATIN,
    x: float = 10,
) -> OCRBlockData:
    return OCRBlockData(
        text=text,
        normalised_text=text,
        confidence=confidence,
        polygon=[
            [x, 10],
            [x + 100, 10],
            [x + 100, 30],
            [x, 30],
        ],
        bbox=OCRBoundingBox(x=x, y=10, width=100, height=20),
        provider_model="test-model",
        recognition_profile=profile,
    )


class StaticProvider(BaseOCRProvider):
    """Injected provider that never imports or downloads a model."""

    def __init__(self, blocks: list[OCRBlockData]) -> None:
        self.blocks = blocks
        self.calls = 0
        self.options: list[dict[str, Any]] = []

    async def recognise_page(
        self,
        image_path: Path,
        language_profile: str,
        options: dict,
    ) -> OCRPageData:
        self.calls += 1
        self.options.append(dict(options))
        assert image_path.is_file()
        return OCRPageData(
            page_number=int(options["page_number"]),
            language_profile=OCRLanguageProfile(language_profile),
            blocks=self.blocks,
        )

    def supports_language_profile(self, language_profile: str) -> bool:
        return language_profile in {profile.value for profile in OCRLanguageProfile}

    def get_provider_info(self) -> dict:
        return {"name": "fake", "version": "test", "processing": "local"}


class MemoryStorage(BaseStorage):
    """Private in-memory object storage for worker orchestration."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    async def save(
        self,
        source: Any,
        storage_key: str,
    ) -> StorageSaveResult:
        payload = source.read()
        self.objects[storage_key] = payload
        return {
            "storage_key": storage_key,
            "storage_provider": "memory",
            "size": len(payload),
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


class LegacyPaddleEngine:
    def __init__(
        self,
        confidence: float = 0.93,
        *,
        text: str = "Document policy",
    ) -> None:
        self.confidence = confidence
        self.text = text

    def ocr(self, _: str, *, cls: bool = True) -> list[object]:
        assert cls is True
        return [
            [
                [
                    [[10, 10], [110, 10], [110, 30], [10, 30]],
                    (self.text, self.confidence),
                ]
            ]
        ]


class ArrayLike:
    """Minimal NumPy-shaped result without making tests depend on NumPy."""

    def __init__(self, value: list[object]) -> None:
        self.value = value

    def tolist(self) -> list[object]:
        return self.value


class MappingPaddleEngine:
    def __init__(
        self,
        *,
        orientation: int | None = None,
        result_object: bool = False,
    ) -> None:
        self.orientation = orientation
        self.result_object = result_object

    def predict(self, *, input: str) -> list[object]:
        assert input
        result: dict[str, object] = {
            "rec_texts": ArrayLike(["Document policy"]),
            "rec_scores": ArrayLike([0.97]),
            "dt_polys": ArrayLike(
                [
                    [
                        [10, 10],
                        [110, 10],
                        [110, 30],
                        [10, 30],
                    ]
                ]
            ),
        }
        if self.orientation is not None:
            result["doc_preprocessor_res"] = {
                "model_settings": {
                    "use_doc_orientation_classify": self.orientation >= 0,
                },
                "angle": self.orientation,
            }
        if self.result_object:
            return [SimpleNamespace(res=result)]
        return [result]


def _extraction_run(total_pages: int = 3) -> ExtractionRun:
    return ExtractionRun(
        extraction_job_id=uuid4(),
        document_id=uuid4(),
        document_revision_id=uuid4(),
        document_file_id=uuid4(),
        extractor_type=ExtractorType.PDF,
        extractor_version="1.0.0",
        status=ExtractionRunStatus.OCR_REQUIRED,
        source_sha256_hash="a" * 64,
        source_file_size=100,
        total_pages=total_pages,
        requires_ocr=True,
        metadata_json={"scannedPages": [2, 3]},
        warnings_json=[],
    )


def test_ocr_metadata_declares_tables_constraints_and_indexes() -> None:
    assert {
        "ocr_jobs",
        "ocr_runs",
        "ocr_page_results",
        "ocr_blocks",
    }.issubset(Base.metadata.tables)
    job_indexes = {index.name for index in Base.metadata.tables["ocr_jobs"].indexes}
    block_indexes = {index.name for index in Base.metadata.tables["ocr_blocks"].indexes}
    assert "uq_ocr_jobs_one_active_per_file" in job_indexes
    assert "ix_ocr_blocks_page_order" in block_indexes
    assert {status.value for status in ACTIVE_OCR_JOB_STATUSES} == {
        "QUEUED",
        "INSPECTING",
        "RENDERING",
        "PREPROCESSING",
        "RECOGNISING",
        "MERGING",
        "PERSISTING",
        "CANCEL_REQUESTED",
    }


def test_public_schema_uses_camel_case_and_validates_pages() -> None:
    payload = OCRStartRequest(
        document_file_id=uuid4(),
        extraction_run_id=uuid4(),
        page_numbers=[3, 1],
    )
    serialized = payload.model_dump(mode="json", by_alias=True)
    assert serialized["documentFileId"]
    assert serialized["extractionRunId"]
    assert serialized["pageNumbers"] == [1, 3]
    with pytest.raises(ValueError):
        OCRStartRequest(
            document_file_id=uuid4(),
            extraction_run_id=uuid4(),
            page_numbers=[1, 1],
        )


@pytest.mark.asyncio
async def test_paddle_provider_supports_profiles_and_parses_legacy_output(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    provider = PaddleOCRProvider(
        engine_factory=lambda _: LegacyPaddleEngine(),
    )
    assert provider.supports_language_profile("LATIN")
    assert provider.supports_language_profile("CHINESE_SIMPLIFIED")
    assert not provider.supports_language_profile("INVALID")
    result = await provider.recognise_page(
        image,
        "LATIN",
        {"page_number": 2, "render_width": 300, "render_height": 200},
    )
    assert result.page_number == 2
    assert result.blocks[0].text == "Document policy"
    assert result.blocks[0].confidence == pytest.approx(0.93)
    assert result.blocks[0].bbox.width == 100


@pytest.mark.asyncio
async def test_paddle_provider_parses_v3_array_like_mapping(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    provider = PaddleOCRProvider(
        engine_factory=lambda _: MappingPaddleEngine(),
    )
    result = await provider.recognise_page(image, "LATIN", {})
    assert [block.text for block in result.blocks] == ["Document policy"]
    assert result.blocks[0].confidence == pytest.approx(0.97)
    assert result.blocks[0].polygon[2] == [110.0, 30.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("orientation", [0, 90, 180, 270])
async def test_paddle_provider_parses_all_document_orientations(
    tmp_path: Path,
    orientation: int,
) -> None:
    image = tmp_path / f"page-{orientation}.png"
    image.write_bytes(b"test")
    provider = PaddleOCRProvider(
        engine_factory=lambda _: MappingPaddleEngine(
            orientation=orientation,
            result_object=True,
        ),
    )

    result = await provider.recognise_page(image, "LATIN", {})

    assert result.rotation_applied == orientation
    assert result.blocks[0].orientation == orientation
    assert result.metadata == {
        "pass": "LATIN",
        "orientation": orientation,
        "orientationDetected": True,
    }


@pytest.mark.asyncio
async def test_paddle_provider_treats_disabled_orientation_as_unavailable(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    provider = PaddleOCRProvider(
        engine_factory=lambda _: MappingPaddleEngine(orientation=-1),
    )

    result = await provider.recognise_page(image, "LATIN", {})

    assert result.rotation_applied == 0
    assert result.blocks[0].orientation == 0
    assert result.metadata == {
        "pass": "LATIN",
        "orientation": 0,
        "orientationDetected": False,
    }


@pytest.mark.asyncio
async def test_paddle_auto_multilingual_runs_both_profiles_and_deduplicates(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    loaded_profiles: list[OCRLanguageProfile] = []

    def engine_factory(profile: OCRLanguageProfile) -> object:
        loaded_profiles.append(profile)
        confidence = 0.98 if profile is OCRLanguageProfile.CHINESE_SIMPLIFIED else 0.93
        return LegacyPaddleEngine(confidence)

    provider = PaddleOCRProvider(engine_factory=engine_factory)
    result = await provider.recognise_page(
        image,
        "AUTO_MULTILINGUAL",
        {},
    )
    assert loaded_profiles == [
        OCRLanguageProfile.LATIN,
        OCRLanguageProfile.CHINESE_SIMPLIFIED,
    ]
    assert result.language_profile is OCRLanguageProfile.AUTO_MULTILINGUAL
    assert result.metadata is not None
    assert result.metadata["passes"] == ["LATIN", "CHINESE_SIMPLIFIED"]
    assert result.metadata["latinBlockCount"] == 1
    assert result.metadata["chineseBlockCount"] == 1
    assert result.metadata["chinesePassEnabled"] is True
    assert result.metadata["chinesePassTriggered"] is True
    assert result.metadata["chinesePassReasons"] == [
        "AUTO_MULTILINGUAL_PROFILE",
        "LOW_LATIN_CHARACTER_COUNT",
    ]
    assert [block.text for block in result.blocks] == ["Document policy"]
    assert result.blocks[0].recognition_profile is OCRLanguageProfile.CHINESE_SIMPLIFIED


@pytest.mark.asyncio
async def test_paddle_auto_multilingual_honours_disabled_chinese_pass(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    loaded_profiles: list[OCRLanguageProfile] = []

    def engine_factory(profile: OCRLanguageProfile) -> object:
        loaded_profiles.append(profile)
        return LegacyPaddleEngine(0.1, text="中文")

    result = await PaddleOCRProvider(engine_factory=engine_factory).recognise_page(
        image,
        "AUTO_MULTILINGUAL",
        {
            "auto_multilingual_chinese_pass": False,
            "force_chinese": True,
        },
    )

    assert loaded_profiles == [OCRLanguageProfile.LATIN]
    assert result.language_profile is OCRLanguageProfile.AUTO_MULTILINGUAL
    assert result.metadata is not None
    assert result.metadata["passes"] == ["LATIN"]
    assert result.metadata["chinesePassEnabled"] is False
    assert result.metadata["chinesePassTriggered"] is False


@pytest.mark.asyncio
async def test_paddle_auto_multilingual_always_runs_configured_chinese_pass(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    loaded_profiles: list[OCRLanguageProfile] = []

    def engine_factory(profile: OCRLanguageProfile) -> object:
        loaded_profiles.append(profile)
        return LegacyPaddleEngine(
            0.99,
            text="This English policy text is confidently recognised.",
        )

    result = await PaddleOCRProvider(engine_factory=engine_factory).recognise_page(
        image,
        "AUTO_MULTILINGUAL",
        {},
    )

    assert loaded_profiles == [
        OCRLanguageProfile.LATIN,
        OCRLanguageProfile.CHINESE_SIMPLIFIED,
    ]
    assert result.metadata is not None
    assert result.metadata["passes"] == ["LATIN", "CHINESE_SIMPLIFIED"]
    assert result.metadata["chinesePassEnabled"] is True
    assert result.metadata["chinesePassTriggered"] is True
    assert result.metadata["chinesePassReasons"] == ["AUTO_MULTILINGUAL_PROFILE"]


@pytest.mark.asyncio
async def test_paddle_auto_multilingual_uses_primary_pass_orientation(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")

    def engine_factory(profile: OCRLanguageProfile) -> object:
        return MappingPaddleEngine(
            orientation=(90 if profile is OCRLanguageProfile.LATIN else 270)
        )

    result = await PaddleOCRProvider(engine_factory=engine_factory).recognise_page(
        image,
        "AUTO_MULTILINGUAL",
        {"force_chinese": True},
    )

    assert result.rotation_applied == 90
    assert result.metadata is not None
    assert result.metadata["passOrientations"] == {
        "LATIN": 90,
        "CHINESE_SIMPLIFIED": 270,
    }
    assert result.metadata["orientationAgreement"] is False


@pytest.mark.asyncio
async def test_paddle_provider_fails_before_implicit_model_download(
    tmp_path: Path,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"test")
    provider = PaddleOCRProvider(model_root=tmp_path / "models")
    with pytest.raises(
        OCRProviderUnavailableError,
        match="local PaddleOCR model files",
    ) as error:
        await provider.recognise_page(image, "LATIN", {})
    assert error.value.code == "OCR_MODEL_LOAD_FAILED"


@pytest.mark.asyncio
async def test_render_applies_dpi_rotation_and_dimension_limit(
    tmp_path: Path,
) -> None:
    source = _pdf(tmp_path / "rotated.pdf", rotation=90)
    rendered = await OCRRenderService(
        dpi=144,
        maximum_width=1000,
        maximum_height=1000,
    ).render_page(source, 1, tmp_path / "render")
    assert rendered.dpi == 144
    assert rendered.source_rotation == 90
    assert rendered.width == 400
    assert rendered.height == 600
    assert rendered.image_path.is_file()

    with pytest.raises(OCRResourceLimitError):
        await OCRRenderService(
            dpi=300,
            maximum_width=100,
            maximum_height=100,
        ).render_page(source, 1, tmp_path / "oversized")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    [
        OCRPreprocessingProfile.STANDARD,
        OCRPreprocessingProfile.AGGRESSIVE,
    ],
)
async def test_preprocessing_creates_private_grayscale_artifact(
    tmp_path: Path,
    profile: OCRPreprocessingProfile,
) -> None:
    source = _pdf(tmp_path / f"{profile.value}.pdf")
    rendered = await OCRRenderService(dpi=72).render_page(
        source,
        1,
        tmp_path / "render",
    )
    service = OCRPreprocessingService()
    preprocessed = await service.preprocess(rendered, profile)
    assert preprocessed.image_path.is_file()
    assert preprocessed.image_path != rendered.image_path
    assert preprocessed.metadata["grayscale"] is True
    await service.remove_preprocessed_page(preprocessed, rendered)
    assert not preprocessed.image_path.exists()
    await OCRRenderService.remove_rendered_page(rendered.image_path)


def test_page_selection_skips_native_text_without_force() -> None:
    run = _extraction_run()
    containers = [
        ExtractedContainer(
            extraction_run_id=run.id,
            container_type=ExtractedContainerType.PDF_PAGE,
            container_index=1,
            name="Page 1",
            raw_text="x" * 100,
            normalised_text="x" * 100,
            character_count=100,
            word_count=1,
        ),
        ExtractedContainer(
            extraction_run_id=run.id,
            container_type=ExtractedContainerType.PDF_PAGE,
            container_index=2,
            name="Page 2",
            raw_text="",
            normalised_text="",
            character_count=0,
            word_count=0,
        ),
        ExtractedContainer(
            extraction_run_id=run.id,
            container_type=ExtractedContainerType.PDF_PAGE,
            container_index=3,
            name="Page 3",
            raw_text="short",
            normalised_text="short",
            character_count=5,
            word_count=1,
        ),
    ]
    service = OCRPageService(
        StaticProvider([]),
        OCRRenderService(),
        OCRPreprocessingService(),
    )
    automatic = service.select_pages(
        run,
        containers,
        requested_page_numbers=None,
        force=False,
    )
    assert automatic.selected_page_numbers == [2, 3]
    manual = service.select_pages(
        run,
        containers,
        requested_page_numbers=[1, 2],
        force=False,
    )
    assert manual.selected_page_numbers == [2]
    assert manual.skipped_page_numbers == [1]
    forced = service.select_pages(
        run,
        containers,
        requested_page_numbers=[1],
        force=True,
    )
    assert forced.selected_page_numbers == [1]


@pytest.mark.asyncio
async def test_page_pipeline_persists_low_confidence_signal_and_cleans_images(
    tmp_path: Path,
) -> None:
    source = _pdf(tmp_path / "source.pdf")
    provider = StaticProvider([_block(confidence=0.2)])
    service = OCRPageService(
        provider,
        OCRRenderService(dpi=72),
        OCRPreprocessingService(),
        low_confidence_threshold=0.6,
    )
    output = tmp_path / "private-temp"
    result = await service.process_page(
        source,
        1,
        output,
        language_profile=OCRLanguageProfile.LATIN,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
    )
    assert result.status is OCRPageStatus.LOW_CONFIDENCE
    assert result.warning_codes == [
        "OCR_LOW_RESOLUTION",
        "OCR_LOW_CONFIDENCE",
    ]
    assert result.metadata is not None
    assert result.metadata["preprocessing"]["resized"] is True
    assert provider.calls == 1
    assert list(output.glob("*.png")) == []


@pytest.mark.asyncio
async def test_page_pipeline_keeps_pdf_rotation_separate_from_ocr_rotation(
    tmp_path: Path,
) -> None:
    source = _pdf(tmp_path / "source.pdf", rotation=90)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    provider = PaddleOCRProvider(
        engine_factory=lambda _: MappingPaddleEngine(
            orientation=270,
            result_object=True,
        ),
    )
    service = OCRPageService(
        provider,
        OCRRenderService(dpi=72),
        OCRPreprocessingService(),
    )

    result = await service.process_page(
        source,
        1,
        tmp_path / "private-temp",
        language_profile=OCRLanguageProfile.LATIN,
        preprocessing_profile=OCRPreprocessingProfile.NONE,
    )

    assert result.rotation_applied == 270
    assert result.blocks[0].orientation == 270
    assert result.metadata is not None
    assert result.metadata["sourceRotation"] == 90
    assert result.metadata["preprocessingRotation"] == 0
    assert result.metadata["providerRotation"] == 270
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    with pymupdf.open(source) as document:
        assert document[0].rotation == 90


@pytest.mark.asyncio
async def test_ocr_service_forwards_bounded_multilingual_settings(
    tmp_path: Path,
) -> None:
    source = _pdf(tmp_path / "source.pdf")
    provider = StaticProvider([_block()])
    settings = get_settings().model_copy(
        update={
            "ocr_auto_multilingual_chinese_pass": False,
            ("ocr_auto_multilingual_chinese_pass_confidence_threshold"): 0.42,
            ("ocr_auto_multilingual_chinese_pass_minimum_characters"): 37,
            "ocr_render_dpi": 72,
        }
    )
    page_service = OCRService(
        settings,
        storage=MemoryStorage({}),
        provider=provider,
    )._page_service()

    await page_service.process_page(
        source,
        1,
        tmp_path / "private-temp",
        language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
        preprocessing_profile=OCRPreprocessingProfile.NONE,
    )

    assert provider.options[0]["auto_multilingual_chinese_pass"] is False
    assert provider.options[0]["chinese_pass_confidence_threshold"] == 0.42
    assert provider.options[0]["chinese_pass_minimum_characters"] == 37


def test_multilingual_merge_deduplicates_overlap_and_preserves_provenance() -> None:
    latin = _block("Document policy", 0.70)
    chinese_pass = _block(
        "Document policy",
        0.95,
        profile=OCRLanguageProfile.CHINESE_SIMPLIFIED,
    )
    merged = OCRMergeService().deduplicate_provider_blocks([latin, chinese_pass])
    assert len(merged) == 1
    assert merged[0].confidence == pytest.approx(0.95)

    unified = OCRMergeService().merge_native_and_ocr(
        [
            {
                "id": uuid4(),
                "page_number": 1,
                "block_order": 1,
                "text": "Native selectable text " * 4,
                "normalised_text": "Native selectable text " * 4,
            }
        ],
        [
            {
                "id": uuid4(),
                "ocr_run_id": uuid4(),
                "ocr_page_result_id": uuid4(),
                "page_number": 1,
                "block_order": 1,
                "text": "Duplicate OCR",
                "normalised_text": "Duplicate OCR",
                "confidence": 0.9,
                "provider_model": "test",
                "recognition_profile": "LATIN",
            },
            {
                "id": uuid4(),
                "ocr_run_id": uuid4(),
                "ocr_page_result_id": uuid4(),
                "page_number": 2,
                "block_order": 1,
                "text": "OCR-only page",
                "normalised_text": "OCR-only page",
                "confidence": 0.88,
                "provider_model": "test",
                "recognition_profile": "LATIN",
            },
        ],
    )
    assert [(item.page_number, item.source) for item in unified] == [
        (1, "NATIVE"),
        (2, "OCR"),
    ]
    assert unified[1].provenance["ocrRunId"]


@pytest.mark.asyncio
async def test_temporary_cleanup_removes_only_stale_owned_directories(
    tmp_path: Path,
) -> None:
    service = OCRTemporaryCleanupService(tmp_path)
    stale = tmp_path / "document-ocr-stale"
    fresh = tmp_path / "document-ocr-fresh"
    unrelated = tmp_path / "other-stale"
    for directory in (stale, fresh, unrelated):
        directory.mkdir()
        (directory / "page.png").write_bytes(b"generated")
    stale_time = datetime.now(UTC).timestamp() - (3 * 60 * 60)
    os.utime(stale, (stale_time, stale_time))
    os.utime(unrelated, (stale_time, stale_time))

    removed = await service.cleanup_stale(retention_hours=2)

    assert removed == [stale]
    assert not stale.exists()
    assert fresh.is_dir()
    assert unrelated.is_dir()
    assert not await service.remove_work_directory(unrelated)
    assert await service.remove_work_directory(fresh)


def _document_graph(
    *,
    file_content: bytes = b"generated-pdf-placeholder",
    requested_pages: list[int] | None = None,
) -> tuple[
    Document,
    DocumentRevision,
    DocumentFile,
    ExtractionRun,
    OCRJob,
]:
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number="007",
        base_document_code="MTI-QMS-POL-007",
        title="Phase 7 OCR Test",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-QMS-POL-007_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename="MTI-QMS-POL-007_Rev.000.pdf",
        sanitized_filename="MTI-QMS-POL-007_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=len(file_content),
        sha256_hash=hashlib.sha256(file_content).hexdigest(),
        storage_key="documents/originals/tests/phase7.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    extraction_job = ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=ExtractionJobStatus.OCR_REQUIRED,
        progress=100,
    )
    extraction_run = ExtractionRun(
        extraction_job=extraction_job,
        document=document,
        revision=revision,
        document_file=document_file,
        extractor_type=ExtractorType.PDF,
        extractor_version="1.0.0",
        status=ExtractionRunStatus.OCR_REQUIRED,
        source_sha256_hash=document_file.sha256_hash,
        source_file_size=document_file.file_size,
        total_pages=len(requested_pages or [1]),
        requires_ocr=True,
        warnings_json=[],
    )
    document_file.latest_extraction_run = extraction_run
    ocr_job = OCRJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        job_type=OCRJobType.INITIAL_OCR,
        status=OCRJobStatus.QUEUED,
        progress=0,
        language_profile=OCRLanguageProfile.LATIN,
        preprocessing_profile=OCRPreprocessingProfile.STANDARD,
        requested_page_numbers_json=requested_pages or [1],
        provider="fake",
    )
    return document, revision, document_file, extraction_run, ocr_job


@pytest.mark.asyncio
async def test_page_persistence_updates_latest_and_retains_provenance(
    session_factory: Any,
) -> None:
    document, revision, document_file, _, job = _document_graph()
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.flush()
        document_file.latest_extraction_run_id = job.extraction_run_id
        await session.flush()
        service = OCRPersistenceService(session)
        run = await service.create_or_get_run(
            job=job,
            document_file=document_file,
            provider_version="test",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        page = await service.persist_page(
            run,
            OCRPageData(
                page_number=1,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[_block()],
            ),
        )
        assert page.block_count == 1
        await service.finalize(
            job=job,
            run=run,
            completed_at=datetime.now(UTC),
        )
        await session.commit()
        await session.refresh(document_file)

        assert job.status is OCRJobStatus.COMPLETED
        assert run.status is OCRRunStatus.COMPLETED
        assert document_file.latest_ocr_run_id == run.id
        assert run.metadata_json is not None
        assert run.metadata_json["latestPointerUpdated"] is True
        stored_run = await OCRRunRepository(session).get_by_id(run.id)
        assert stored_run is not None
        blocks = await session.get(
            OCRBlock,
            (
                await session.scalar(
                    select(OCRBlock.id).where(OCRBlock.ocr_run_id == run.id)
                )
            ),
        )
        assert blocks is not None
        assert blocks.provider_model == "test-model"
        assert blocks.confidence == pytest.approx(0.9)
        stored_page = await session.get(OCRPageResult, page.id)
        assert stored_page is not None
        assert stored_page.content_hash is not None

        stale_update = await OCRRunRepository(session).set_latest_by_ids(
            document_file_id=document_file.id,
            ocr_run_id=uuid4(),
            source_extraction_run_id=uuid4(),
        )
        assert stale_update is False
        assert document_file.latest_ocr_run_id == run.id

        await ExtractionRunRepository(session).set_latest(
            document_file,
            job.extraction_run,
        )
        assert document_file.latest_ocr_run_id is None
        assert document_file.latest_language_detection_run_id is None


@pytest.mark.asyncio
async def test_ocr_summary_persists_configured_low_confidence_count(
    session_factory: Any,
) -> None:
    document, revision, document_file, _, job = _document_graph()
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.flush()
        service = OCRPersistenceService(
            session,
            low_confidence_threshold=0.55,
            review_confidence_threshold=0.75,
        )
        run = await service.create_or_get_run(
            job=job,
            document_file=document_file,
            provider_version="test",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await service.persist_page(
            run,
            OCRPageData(
                page_number=1,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[
                    _block("Low confidence", confidence=0.40),
                    _block("High confidence", confidence=0.90, x=140),
                ],
            ),
        )
        await service.finalize(
            job=job,
            run=run,
            completed_at=datetime.now(UTC),
        )

        assert run.metadata_json is not None
        assert run.metadata_json["lowConfidenceBlocks"] == 1
        assert run.metadata_json["lowConfidenceThreshold"] == pytest.approx(0.55)
        assert run.metadata_json["reviewConfidenceThreshold"] == pytest.approx(0.75)
        assert job.result_summary_json is not None
        assert job.result_summary_json["provider"] == job.provider
        assert job.result_summary_json["providerVersion"] == "test"
        assert job.result_summary_json["lowConfidenceBlocks"] == 1
        counts = await OCRBlockRepository(session).count_below_confidence_by_run(
            [run.id],
            threshold=0.55,
        )
        assert counts == {run.id: 1}


@pytest.mark.asyncio
async def test_terminal_worker_failure_never_completes_an_incomplete_run(
    session_factory: Any,
) -> None:
    document, revision, document_file, _, job = _document_graph(
        requested_pages=[1, 2, 3]
    )
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.flush()
        service = OCRPersistenceService(session)
        run = await service.create_or_get_run(
            job=job,
            document_file=document_file,
            provider_version="test",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await service.persist_page(
            run,
            OCRPageData(
                page_number=1,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[_block("Only the first page completed")],
            ),
        )

        await service.finalize(
            job=job,
            run=run,
            completed_at=datetime.now(UTC),
            terminal_failure=True,
        )

        assert run.status is OCRRunStatus.PARTIALLY_COMPLETED
        assert run.page_count_processed == 1
        assert run.page_count_failed == 2
        assert job.processed_page_numbers_json == [1]
        assert job.failed_page_numbers_json == [2, 3]
        assert job.result_summary_json is not None
        assert job.result_summary_json["status"] == "PARTIALLY_COMPLETED"
        assert job.result_summary_json["terminalFailure"] is True
        assert job.result_summary_json["unpersistedPageNumbers"] == [2, 3]


@pytest.mark.asyncio
async def test_ocr_job_repository_filters_profile_and_honours_sorting(
    session_factory: Any,
) -> None:
    document, revision, document_file, extraction_run, first_job = _document_graph()
    now = datetime.now(UTC)
    first_job.status = OCRJobStatus.COMPLETED
    first_job.progress = 100
    first_job.requested_at = now - timedelta(minutes=2)
    first_job.completed_at = now - timedelta(minutes=1)
    second_job = OCRJob(
        document=document,
        revision=revision,
        document_file=document_file,
        extraction_run=extraction_run,
        job_type=OCRJobType.RE_OCR,
        status=OCRJobStatus.COMPLETED,
        progress=100,
        language_profile=OCRLanguageProfile.CHINESE_SIMPLIFIED,
        preprocessing_profile=OCRPreprocessingProfile.AGGRESSIVE,
        requested_page_numbers_json=[1],
        processed_page_numbers_json=[1],
        provider="fake",
        requested_at=now,
        completed_at=now,
    )

    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_run,
                first_job,
                second_job,
            ]
        )
        await session.commit()
        repository = OCRJobRepository(session)

        latin_jobs, latin_total = await repository.list(
            language_profile=OCRLanguageProfile.LATIN,
            scope_all_departments=True,
            scope_department_id=None,
        )
        assert latin_total == 1
        assert [job.id for job in latin_jobs] == [first_job.id]

        sorted_jobs, sorted_total = await repository.list(
            search=revision.full_document_code,
            scope_all_departments=True,
            scope_department_id=None,
            sort_by="completedAt",
            sort_order="asc",
        )
        assert sorted_total == 2
        assert [job.id for job in sorted_jobs] == [
            first_job.id,
            second_job.id,
        ]


@pytest.mark.asyncio
async def test_worker_pipeline_completes_multiple_pages_with_fake_provider(
    session_factory: Any,
) -> None:
    source = _pdf_bytes(page_count=2)
    document, revision, document_file, _, job = _document_graph(
        file_content=source,
        requested_pages=[1, 2],
    )
    storage_key = document_file.storage_key
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()
        job_id = job.id
        file_id = document_file.id

    provider = StaticProvider([_block()])
    status = await OCRService(
        get_settings(),
        session_factory=session_factory,
        storage=MemoryStorage({storage_key: source}),
        provider=provider,
    ).process_job(
        job_id,
        worker_reference="test-worker",
    )

    async with session_factory() as session:
        stored_job = await OCRJobRepository(session).get_by_id(job_id)
        assert stored_job is not None
        assert status is OCRJobStatus.COMPLETED, (
            stored_job.error_code,
            stored_job.error_message,
        )
        assert provider.calls == 2
        assert stored_job.processed_page_numbers_json == [1, 2]
        assert stored_job.failed_page_numbers_json == []
        run = await OCRRunRepository(session).get_latest_by_file(file_id)
        assert run is not None
        assert run.status is OCRRunStatus.COMPLETED
        assert run.total_blocks == 2
        pages, total = await OCRPageResultRepository(session).list_by_run(run.id)
        assert total == 2
        assert [page.page_number for page in pages] == [1, 2]


@pytest.mark.asyncio
async def test_worker_provider_failure_retains_only_a_partial_run(
    session_factory: Any,
) -> None:
    source = _pdf_bytes(page_count=2)
    document, revision, document_file, _, job = _document_graph(
        file_content=source,
        requested_pages=[1, 2],
    )
    storage_key = document_file.storage_key
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()
        job_id = job.id

    class FailOnSecondPageProvider(StaticProvider):
        async def recognise_page(
            self,
            image_path: Path,
            language_profile: str,
            options: dict,
        ) -> OCRPageData:
            if self.calls == 1:
                self.calls += 1
                raise RuntimeError("generated provider failure")
            return await super().recognise_page(
                image_path,
                language_profile,
                options,
            )

    provider = FailOnSecondPageProvider([_block()])
    status = await OCRService(
        get_settings(),
        session_factory=session_factory,
        storage=MemoryStorage({storage_key: source}),
        provider=provider,
    ).process_job(job_id, worker_reference="test-worker")

    async with session_factory() as session:
        stored_job = await OCRJobRepository(session).get_by_id(job_id)
        run = await OCRRunRepository(session).get_by_job_id(job_id)
        assert status is OCRJobStatus.FAILED
        assert stored_job is not None
        assert stored_job.status is OCRJobStatus.FAILED
        assert stored_job.error_code == "OCR_RECOGNITION_FAILED"
        assert stored_job.processed_page_numbers_json == [1]
        assert stored_job.failed_page_numbers_json == [2]
        assert run is not None
        assert run.status is OCRRunStatus.PARTIALLY_COMPLETED
        assert run.page_count_processed == 1
        assert run.page_count_failed == 1
        assert run.metadata_json is not None
        assert run.metadata_json["terminalFailure"] is True


@pytest.mark.asyncio
async def test_worker_honours_cancel_before_loading_provider(
    session_factory: Any,
) -> None:
    source = _pdf_bytes()
    document, revision, document_file, _, job = _document_graph(file_content=source)
    storage_key = document_file.storage_key
    job.status = OCRJobStatus.CANCEL_REQUESTED
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.commit()
        job_id = job.id

    provider = StaticProvider([_block()])
    status = await OCRService(
        get_settings(),
        session_factory=session_factory,
        storage=MemoryStorage({storage_key: source}),
        provider=provider,
    ).process_job(job_id)
    assert status is OCRJobStatus.CANCELLED
    assert provider.calls == 0
    async with session_factory() as session:
        stored_job = await OCRJobRepository(session).get_by_id(job_id)
        assert stored_job is not None
        assert stored_job.status is OCRJobStatus.CANCELLED


@pytest.mark.asyncio
async def test_job_service_queues_selected_page_and_rejects_duplicate(
    session_factory: Any,
    create_user: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _pdf_bytes()
    document, revision, document_file, extraction_run, _ = _document_graph(
        file_content=source
    )
    department_user = await create_user(
        email="phase7-ocr-user@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=document.department_id,
    )
    container = ExtractedContainer(
        extraction_run=extraction_run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=1,
        name="Page 1",
        raw_text="",
        normalised_text="",
        character_count=0,
        word_count=0,
    )
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_run,
                container,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = extraction_run.id
        await session.commit()
        file_id = document_file.id
        extraction_run_id = extraction_run.id

    monkeypatch.setattr(
        process_ocr_job,
        "apply_async",
        lambda **_: SimpleNamespace(id="phase7-ocr-task"),
    )
    async with session_factory() as session:
        service = OCRJobService(
            session,
            get_settings(),
            department_user,
            RequestMetadata(ip_address=None, user_agent="pytest"),
        )
        queued = await service.start(
            OCRStartRequest(
                document_file_id=file_id,
                extraction_run_id=extraction_run_id,
            )
        )
        assert queued.status is OCRJobStatus.QUEUED
        assert queued.page_numbers == [1]
        with pytest.raises(ApplicationError, match="Active OCR job"):
            await service.start(
                OCRStartRequest(
                    document_file_id=file_id,
                    extraction_run_id=extraction_run_id,
                )
            )


@pytest.mark.asyncio
async def test_initial_ocr_cannot_bypass_latest_source_with_reocr_permission(
    session_factory: Any,
    create_user: Any,
) -> None:
    document, revision, document_file, extraction_run, _ = _document_graph()
    controller = await create_user(
        email="phase7-ocr-controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=document.department_id,
    )
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_run,
            ]
        )
        await session.flush()
        document_file.latest_extraction_run_id = None
        await session.commit()

        service = OCRJobService(
            session,
            get_settings(),
            controller,
            RequestMetadata(ip_address=None, user_agent="pytest"),
        )
        with pytest.raises(ApplicationError) as raised:
            await service.start(
                OCRStartRequest(
                    document_file_id=document_file.id,
                    extraction_run_id=extraction_run.id,
                )
            )

        assert raised.value.status_code == 400
        assert raised.value.errors is not None
        assert raised.value.errors[0].field == "extractionRunId"
        assert "latest extraction" in raised.value.errors[0].message


@pytest.mark.asyncio
async def test_initial_or_forced_start_cannot_bypass_reasoned_reocr(
    session_factory: Any,
    create_user: Any,
) -> None:
    document, revision, document_file, extraction_run, job = _document_graph()
    controller = await create_user(
        email="phase7-ocr-existing-controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=document.department_id,
    )
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.flush()
        persistence = OCRPersistenceService(session)
        run = await persistence.create_or_get_run(
            job=job,
            document_file=document_file,
            provider_version="test",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await persistence.persist_page(
            run,
            OCRPageData(
                page_number=1,
                language_profile=OCRLanguageProfile.LATIN,
                render_width=1200,
                render_height=1600,
                render_dpi=300,
                blocks=[_block()],
            ),
        )
        await persistence.finalize(
            job=job,
            run=run,
            completed_at=datetime.now(UTC),
        )
        await session.commit()

        service = OCRJobService(
            session,
            get_settings(),
            controller,
            RequestMetadata(ip_address=None, user_agent="pytest"),
        )
        for force in (False, True):
            with pytest.raises(ApplicationError) as raised:
                await service.start(
                    OCRStartRequest(
                        document_file_id=document_file.id,
                        extraction_run_id=extraction_run.id,
                        page_numbers=[1],
                        force=force,
                    )
                )

            assert raised.value.status_code == 409
            assert raised.value.errors is not None
            assert raised.value.errors[0].field == "documentFileId"
            assert "re-OCR endpoint" in raised.value.errors[0].message


@pytest.mark.asyncio
async def test_reocr_rejects_a_failed_source_run(
    session_factory: Any,
    create_user: Any,
) -> None:
    document, revision, document_file, _, job = _document_graph()
    controller = await create_user(
        email="phase7-ocr-failed-controller@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=document.department_id,
    )
    async with session_factory() as session:
        session.add_all([document, revision, document_file, job])
        await session.flush()
        run = await OCRPersistenceService(session).create_or_get_run(
            job=job,
            document_file=document_file,
            provider_version="test",
            render_dpi=300,
            started_at=datetime.now(UTC),
        )
        await session.commit()

        service = OCRJobService(
            session,
            get_settings(),
            controller,
            RequestMetadata(ip_address=None, user_agent="pytest"),
        )
        with pytest.raises(ApplicationError) as raised:
            await service.reocr(
                run.id,
                OCRReprocessRequest(reason="Retry a failed OCR run."),
            )

        assert raised.value.status_code == 400
        assert raised.value.errors is not None
        assert raised.value.errors[0].field == "runId"
