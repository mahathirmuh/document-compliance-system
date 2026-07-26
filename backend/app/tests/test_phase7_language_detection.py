"""Focused Phase 7 tests for hybrid local language detection."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityReason,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.schemas.language_detection import LanguageDetectionStartRequest
from app.schemas.language_internal import LanguageSourceBlockData
from app.services.language.base_language_detector import (
    LanguageModelNotAvailableError,
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
from app.services.language.language_detection_service import (
    LanguageDetectionCancelledError,
    LanguageDetectionService,
    LanguagePipelineError,
)
from app.services.language.language_normalizer import (
    LanguageEligibilityEvaluator,
    calculate_source_content_hash,
    calculate_source_snapshot_hash,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.services.language.unicode_script_detector import (
    UnicodeScriptDetector,
)


class AdaptivePredictor:
    """Small deterministic substitute for lid.176 in unit tests."""

    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]:
        del k
        lowered = text.casefold()
        has_han = any("\u3400" <= character <= "\u9fff" for character in text)
        if "bonjour" in lowered:
            return ["__label__fr", "__label__en"], [0.92, 0.03]
        if "ambiguous" in lowered:
            return ["__label__en", "__label__id"], [0.40, 0.35]
        if has_han and any(
            character.isascii() and character.isalpha() for character in text
        ):
            return ["__label__en", "__label__zh"], [0.55, 0.40]
        if has_han:
            return ["__label__zh", "__label__en"], [0.88, 0.04]
        if "shall" in lowered and "untuk" in lowered:
            return ["__label__id", "__label__en"], [0.50, 0.45]
        if any(
            word in lowered.split() for word in ("yang", "untuk", "dengan", "adalah")
        ):
            return ["__label__id", "__label__en"], [0.88, 0.06]
        return ["__label__en", "__label__id"], [0.90, 0.04]


class WeakSecondaryPredictor:
    """Keep the model secondary below the mixed-language threshold."""

    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]:
        del k
        has_han = any("\u3400" <= character <= "\u9fff" for character in text)
        if has_han:
            return ["__label__zh", "__label__en"], [0.97, 0.01]
        return ["__label__id", "__label__en"], [0.97, 0.01]


class WeakPrimaryPredictor:
    """Return only weak absolute evidence for an otherwise neutral sentence."""

    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]:
        del text, k
        return ["__label__en"], [0.10]


class CopyBugNativeBinding:
    def predict(
        self,
        text: str,
        k: int,
        threshold: float,
        on_unicode_error: str,
    ) -> list[tuple[float, str]]:
        assert text.endswith("\n")
        assert k == 5
        assert threshold == 0.0
        assert on_unicode_error == "strict"
        return [(0.9, "__label__en"), (0.05, "__label__id")]


class CopyBugPredictor:
    """Emulate fasttext-wheel's NumPy 2 copy=False wrapper failure."""

    f = CopyBugNativeBinding()

    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]:
        del text, k
        raise ValueError("Unable to avoid copy while creating an array")


@pytest.fixture
def runtime_config() -> LanguageRuntimeConfig:
    return LanguageRuntimeConfig(
        model_path=Path("unused-in-injected-tests.bin"),
    )


@pytest.fixture
def detector(runtime_config: LanguageRuntimeConfig) -> HybridLanguageDetector:
    return HybridLanguageDetector(
        FastTextLanguageDetector(
            runtime_config.model_path,
            predictor=AdaptivePredictor(),
        ),
        runtime_config,
    )


def _source(
    text: str,
    *,
    container_index: int = 1,
    block_order: int = 1,
    page_number: int | None = None,
    source_type: LanguageSourceType = (LanguageSourceType.NATIVE_EXTRACTION),
) -> LanguageSourceBlockData:
    is_native = source_type is LanguageSourceType.NATIVE_EXTRACTION
    return LanguageSourceBlockData(
        source_type=source_type,
        extracted_block_id=uuid4() if is_native else None,
        ocr_block_id=None if is_native else uuid4(),
        container_id=uuid4(),
        container_type="PDF_PAGE",
        container_name=f"Page {container_index}",
        container_index=container_index,
        page_number=page_number,
        block_order=block_order,
        source_reference=f"source:{container_index}:{block_order}",
        text=text,
        normalised_text=text,
        source_confidence=0.9 if not is_native else None,
    )


def test_unicode_script_detector_counts_latin_han_and_nonletters() -> None:
    result = UnicodeScriptDetector().analyse("Abc 文件 123!")

    assert result.latin_character_count == 3
    assert result.han_character_count == 2
    assert result.digit_count == 3
    assert result.punctuation_count == 1
    assert result.dominant_script.value == "MIXED"
    assert result.han_ratio == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", LanguageEligibilityReason.EMPTY),
        ("12345", LanguageEligibilityReason.NO_LETTERS),
        ("https://example.com/x", LanguageEligibilityReason.URL_ONLY),
        ("team@example.com", LanguageEligibilityReason.EMAIL_ONLY),
        ("ISO-9001", LanguageEligibilityReason.CODE_LIKE_TEXT),
        ("ab", LanguageEligibilityReason.TOO_SHORT),
    ],
)
def test_language_eligibility_excludes_nonlinguistic_text(
    runtime_config: LanguageRuntimeConfig,
    text: str,
    reason: LanguageEligibilityReason,
) -> None:
    result = LanguageEligibilityEvaluator(runtime_config).evaluate(text)

    assert result.status is LanguageEligibilityStatus.INELIGIBLE
    assert result.reason is reason


def test_language_eligibility_accepts_normal_paragraph(
    runtime_config: LanguageRuntimeConfig,
) -> None:
    result = LanguageEligibilityEvaluator(runtime_config).evaluate(
        "Dokumen ini berlaku untuk seluruh departemen."
    )

    assert result.status is LanguageEligibilityStatus.ELIGIBLE
    assert result.reason is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Dokumen ini adalah prosedur yang berlaku untuk seluruh bagian.",
            LanguageCode.INDONESIAN,
        ),
        (
            "This document shall apply to the complete control procedure.",
            LanguageCode.ENGLISH,
        ),
        ("文件控制程序适用于所有部门。", LanguageCode.CHINESE),
        ("Bonjour et merci pour cette procédure complète.", LanguageCode.OTHER),
        (
            "This ambiguous technical phrase has weak evidence.",
            LanguageCode.UNKNOWN,
        ),
    ],
)
def test_hybrid_detector_distinguishes_target_other_and_unknown(
    detector: HybridLanguageDetector,
    text: str,
    expected: LanguageCode,
) -> None:
    result = detector.detect(text)

    assert result.language_code is expected
    assert 0 <= result.confidence <= 1


def test_weak_primary_evidence_remains_unknown_after_candidate_normalization(
    runtime_config: LanguageRuntimeConfig,
) -> None:
    detector = HybridLanguageDetector(
        FastTextLanguageDetector(
            runtime_config.model_path,
            predictor=WeakPrimaryPredictor(),
        ),
        runtime_config,
    )

    result = detector.detect("Alpha omega gamma lambda epsilon zeta.")

    assert result.language_code is LanguageCode.UNKNOWN
    assert result.primary_language_code is LanguageCode.ENGLISH
    assert result.confidence == pytest.approx(0.10)
    assert result.confidence <= runtime_config.confidence_minimum
    assert len(result.detected_languages) == 1
    assert result.detected_languages[0].language_code is LanguageCode.ENGLISH
    assert result.detected_languages[0].score == pytest.approx(1.0)


def test_hybrid_detector_finds_latin_han_mixed_language(
    detector: HybridLanguageDetector,
) -> None:
    result = detector.detect(
        "Document control 文件控制程序 procedure applies 文件控制程序 to every unit."
    )

    assert result.language_code is LanguageCode.MIXED
    assert result.is_mixed is True
    assert {score.language_code for score in result.detected_languages[:2]} == {
        LanguageCode.ENGLISH,
        LanguageCode.CHINESE,
    }


def test_hybrid_detector_finds_indonesian_english_mixed_language(
    detector: HybridLanguageDetector,
) -> None:
    result = detector.detect(
        "Prosedur ini shall apply untuk document control dan the reviewer."
    )

    assert result.language_code is LanguageCode.MIXED
    assert result.primary_language_code in {
        LanguageCode.INDONESIAN,
        LanguageCode.ENGLISH,
    }


def test_strong_dual_lexical_evidence_overrides_weak_model_secondary(
    runtime_config: LanguageRuntimeConfig,
) -> None:
    detector = HybridLanguageDetector(
        FastTextLanguageDetector(
            runtime_config.model_path,
            predictor=WeakSecondaryPredictor(),
        ),
        runtime_config,
    )

    result = detector.detect(
        "Prosedur ini shall apply untuk document control dan the reviewer."
    )

    assert result.language_code is LanguageCode.MIXED
    assert result.is_mixed is True
    assert result.metadata["lexicalSignals"] == {
        "id": pytest.approx(0.375),
        "en": pytest.approx(0.375),
    }


def test_strong_han_latin_evidence_overrides_weak_model_secondary(
    runtime_config: LanguageRuntimeConfig,
) -> None:
    detector = HybridLanguageDetector(
        FastTextLanguageDetector(
            runtime_config.model_path,
            predictor=WeakSecondaryPredictor(),
        ),
        runtime_config,
    )

    result = detector.detect(
        "Document control 文件控制程序 applies to every unit 文件."
    )

    assert result.language_code is LanguageCode.MIXED
    assert result.is_mixed is True
    assert (
        result.script_statistics.han_ratio >= runtime_config.mixed_min_character_ratio
    )
    assert (
        result.script_statistics.latin_ratio >= runtime_config.mixed_min_character_ratio
    )


def test_ineligible_code_never_loads_fasttext(
    runtime_config: LanguageRuntimeConfig,
) -> None:
    missing = FastTextLanguageDetector(Path("definitely-missing.bin"))
    detector = HybridLanguageDetector(missing, runtime_config)

    result = detector.detect("ISO-9001")

    assert result.language_code is LanguageCode.UNKNOWN
    assert result.eligibility.reason is LanguageEligibilityReason.CODE_LIKE_TEXT


def test_eligible_text_fails_closed_when_model_is_missing(
    runtime_config: LanguageRuntimeConfig,
    tmp_path: Path,
) -> None:
    missing = FastTextLanguageDetector(tmp_path / "missing.bin")
    detector = HybridLanguageDetector(missing, runtime_config)

    with pytest.raises(LanguageModelNotAvailableError):
        detector.detect("This paragraph contains enough linguistic evidence.")


def test_fasttext_numpy_two_compatibility_uses_native_binding() -> None:
    detector = FastTextLanguageDetector(
        Path("injected.bin"),
        predictor=CopyBugPredictor(),
    )

    scores = detector.predict_scores("This is an English paragraph.")

    assert scores[0].language_code is LanguageCode.ENGLISH
    assert scores[0].score == pytest.approx(0.9)


def test_source_hashes_are_deterministic_and_provenance_sensitive() -> None:
    first = _source("Hello world")
    second = first.model_copy(
        update={
            "text": "Changed text",
            "normalised_text": "Changed text",
        }
    )

    assert calculate_source_content_hash([first]) == (
        calculate_source_content_hash([first])
    )
    assert calculate_source_content_hash([first]) != (
        calculate_source_content_hash([second])
    )
    assert calculate_source_snapshot_hash("a" * 64, None) == (
        calculate_source_snapshot_hash("a" * 64, None)
    )
    assert calculate_source_snapshot_hash("a" * 64, None) != (
        calculate_source_snapshot_hash("a" * 64, "b" * 64)
    )


@pytest.mark.asyncio
async def test_pipeline_detects_native_and_ocr_with_injected_model(
    detector: HybridLanguageDetector,
) -> None:
    settings = SimpleNamespace()
    service = LanguageDetectionService(
        settings,  # type: ignore[arg-type]
        detector=detector,
    )
    sources = [
        _source(
            "Dokumen ini adalah prosedur yang berlaku untuk semua bagian.",
            page_number=1,
        ),
        _source(
            "文件控制程序适用于所有部门。",
            container_index=2,
            page_number=2,
            source_type=LanguageSourceType.OCR,
        ),
    ]

    detected = await service.detect_sources(sources)
    pipeline = service.build_pipeline_result(
        detected,
        source_content_hash="a" * 64,
    )

    assert [item.detection.language_code for item in detected] == [
        LanguageCode.INDONESIAN,
        LanguageCode.CHINESE,
    ]
    assert pipeline.aggregate.total_blocks == 2
    assert len(pipeline.containers) == 2


def test_pipeline_maps_aggregation_failure_to_stable_error(
    detector: HybridLanguageDetector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LanguageDetectionService(
        SimpleNamespace(),  # type: ignore[arg-type]
        detector=detector,
    )

    def fail_aggregation(_blocks: object) -> object:
        raise RuntimeError("synthetic aggregation failure")

    monkeypatch.setattr(
        service.aggregation,
        "aggregate_containers",
        fail_aggregation,
    )

    with pytest.raises(LanguagePipelineError) as raised:
        service.build_pipeline_result(
            [],
            source_content_hash="a" * 64,
        )

    assert raised.value.code == "LANGUAGE_AGGREGATION_FAILED"


@pytest.mark.asyncio
async def test_pipeline_checks_cooperative_cancellation(
    detector: HybridLanguageDetector,
) -> None:
    service = LanguageDetectionService(
        SimpleNamespace(),  # type: ignore[arg-type]
        detector=detector,
    )

    async def cancelled() -> bool:
        return True

    with pytest.raises(LanguageDetectionCancelledError):
        await service.detect_sources(
            [_source("This document shall apply to every department.")],
            cancellation_checker=cancelled,
        )


def test_merge_prefers_sufficient_native_page_and_deduplicates_ocr(
    detector: HybridLanguageDetector,
) -> None:
    service = LanguageDetectionService(
        SimpleNamespace(),  # type: ignore[arg-type]
        detector=detector,
    )
    long_native = _source(
        "Native selectable text " * 4,
        page_number=1,
    )
    short_native = _source(
        "Short native",
        container_index=2,
        page_number=2,
    )
    skipped_ocr = _source(
        "OCR addition should be skipped on native-rich page",
        page_number=1,
        source_type=LanguageSourceType.OCR,
    )
    duplicate_ocr = _source(
        "Short native",
        container_index=2,
        page_number=2,
        source_type=LanguageSourceType.OCR,
    )
    retained_ocr = _source(
        "OCR-only Chinese 文件内容",
        container_index=2,
        block_order=2,
        page_number=2,
        source_type=LanguageSourceType.OCR,
    )
    repeated_ocr = retained_ocr.model_copy(
        update={
            "ocr_block_id": uuid4(),
            "source_reference": "duplicate-pass",
        }
    )

    merged = service.merge_sources(
        [long_native, short_native],
        [skipped_ocr, duplicate_ocr, retained_ocr, repeated_ocr],
    )

    assert [item.source_reference for item in merged] == [
        long_native.source_reference,
        short_native.source_reference,
        retained_ocr.source_reference,
    ]


def test_aggregation_uses_presence_threshold_and_preliminary_coverage(
    detector: HybridLanguageDetector,
    runtime_config: LanguageRuntimeConfig,
) -> None:
    sources = [
        _source(
            "Dokumen ini adalah prosedur yang berlaku untuk seluruh bagian.",
            block_order=1,
        ),
        _source(
            "Setiap pengguna harus mengikuti prosedur yang telah ditetapkan.",
            block_order=2,
        ),
        _source(
            "This document shall apply to the complete control procedure.",
            block_order=3,
        ),
        _source(
            "The reviewer must follow this procedure with proper records.",
            block_order=4,
        ),
        _source("ISO-9001", block_order=5),
    ]
    detected = [
        # The detector is synchronous by design; aggregate uses retained DTOs.
        (
            source,
            detector.detect(source.text),
        )
        for source in sources
    ]
    from app.schemas.language_internal import DetectedLanguageBlockData

    blocks = [
        DetectedLanguageBlockData(source=source, detection=result)
        for source, result in detected
    ]
    aggregate = LanguageAggregationService(runtime_config).aggregate(blocks)

    assert aggregate.coverage.preliminary is True
    assert aggregate.coverage.language_presence.id.value == "PRESENT"
    assert aggregate.coverage.language_presence.en.value == "PRESENT"
    assert aggregate.coverage.language_presence.zh.value == "NOT_PRESENT"
    assert aggregate.eligible_blocks == 4
    assert aggregate.unknown_blocks == 1
    total_coverage = sum(aggregate.coverage.block_coverage.model_dump().values())
    assert total_coverage == pytest.approx(100.0, abs=0.05)


def test_public_schema_serializes_camel_case() -> None:
    payload = LanguageDetectionStartRequest(
        document_file_id=uuid4(),
        extraction_run_id=uuid4(),
    )

    serialized = payload.model_dump(by_alias=True, mode="json")

    assert "documentFileId" in serialized
    assert "extractionRunId" in serialized
    assert "ocrRunId" in serialized
