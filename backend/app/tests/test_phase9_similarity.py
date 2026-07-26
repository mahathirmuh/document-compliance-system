"""Focused regression coverage for the Phase 9 similarity domain."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import configure_mappers

import app.models.similarity_job
import app.models.similarity_result
import app.models.similarity_run
import app.models.similarity_section_summary
from app.api.v1.endpoints.similarity import router as similarity_router
from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityCategory,
    SimilarityRunStatus,
)
from app.models.similarity_job import SimilarityJob
from app.models.similarity_result import TranslationSimilarityResult
from app.models.similarity_run import SimilarityRun
from app.models.similarity_section_summary import SectionSimilaritySummary
from app.repositories.section_similarity_repository import (
    SectionSimilarityRepository,
)
from app.repositories.similarity_job_repository import (
    SimilarityJobRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.repositories.translation_similarity_repository import (
    TranslationSimilarityRepository,
)
from app.schemas.similarity import (
    SimilarityRerunRequest,
    SimilarityStartRequest,
)
from app.schemas.similarity_internal import (
    SimilarityContext,
    SimilarityGroupData,
    SimilarityMemberData,
    SimilarityOptions,
)
from app.services.similarity.alignment.long_text_chunking_service import (
    LongTextChunkingService,
)
from app.services.similarity.alignment.text_eligibility_service import (
    TextEligibilityService,
)
from app.services.similarity.base_similarity_provider import (
    SimilarityProviderUnavailable,
)
from app.services.similarity.consistency.date_consistency_service import (
    DateConsistencyService,
)
from app.services.similarity.consistency.measurement_consistency_service import (
    MeasurementConsistencyService,
)
from app.services.similarity.consistency.negation_mismatch_service import (
    NegationMismatchService,
)
from app.services.similarity.consistency.number_consistency_service import (
    NumberConsistencyService,
)
from app.services.similarity.consistency.reference_consistency_service import (
    ReferenceConsistencyService,
)
from app.services.similarity.deterministic_similarity_provider import (
    DeterministicSimilarityProvider,
)
from app.services.similarity.sentence_transformer_provider import (
    SentenceTransformerProvider,
)
from app.services.similarity.similarity_provider_factory import (
    SimilarityProviderFactory,
)
from app.services.similarity.similarity_score_service import (
    SimilarityScoreService,
)
from app.services.similarity.translation_similarity_service import (
    SimilarityAnalysisCancelled,
    TranslationSimilarityService,
)


def test_similarity_models_register_the_four_required_tables() -> None:
    configure_mappers()
    tables = app.models.similarity_job.Base.metadata.tables
    assert {
        "similarity_jobs",
        "similarity_runs",
        "translation_similarity_results",
        "section_similarity_summaries",
    }.issubset(tables)
    result_columns = tables["translation_similarity_results"].columns
    assert "source_text_hash" in result_columns
    assert "target_text_hash" in result_columns
    assert "source_text" not in result_columns
    assert "target_text" not in result_columns


def test_public_schemas_emit_camel_case_and_require_rerun_reason() -> None:
    file_id = uuid4()
    payload = SimilarityStartRequest(documentFileId=file_id)
    assert payload.document_file_id == file_id
    assert payload.model_dump(by_alias=True)["documentFileId"] == file_id
    assert SimilarityRerunRequest(reason="  model updated  ").reason == (
        "model updated"
    )
    with pytest.raises(ValidationError):
        SimilarityRerunRequest(reason="   ")


def test_similarity_router_exposes_the_complete_contract() -> None:
    paths = {
        (method, route.path)
        for route in similarity_router.routes
        for method in route.methods
    }
    assert ("POST", "/similarity/jobs") in paths
    assert ("GET", "/similarity/jobs") in paths
    assert ("POST", "/similarity/jobs/{job_id}/cancel") in paths
    assert ("GET", "/similarity/runs/{run_id}/results") in paths
    assert ("GET", "/similarity/runs/{run_id}/sections") in paths
    assert ("GET", "/similarity/runs/{run_id}/export") in paths
    assert ("POST", "/similarity/runs/{run_id}/rerun") in paths
    assert ("GET", "/document-files/{file_id}/similarity") in paths
    assert (
        "GET",
        "/document-files/{file_id}/similarity-history",
    ) in paths


@pytest.mark.asyncio
async def test_similarity_repositories_persist_and_filter_bounded_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document_id = uuid4()
    revision_id = uuid4()
    file_id = uuid4()
    compliance_id = uuid4()
    language_id = uuid4()
    group_id = uuid4()
    section_id = uuid4()
    async with session_factory() as session:
        job = SimilarityJob(
            document_id=document_id,
            document_revision_id=revision_id,
            document_file_id=file_id,
            compliance_run_id=compliance_id,
            language_detection_run_id=language_id,
            source_content_hash="a" * 64,
            provider="deterministic",
            model_name="test-provider",
        )
        await SimilarityJobRepository(session).add(job)
        run = SimilarityRun(
            similarity_job_id=job.id,
            document_id=document_id,
            document_revision_id=revision_id,
            document_file_id=file_id,
            compliance_run_id=compliance_id,
            language_detection_run_id=language_id,
            provider="deterministic",
            model_name="test-provider",
            model_version="1",
            status=SimilarityRunStatus.COMPLETED,
            source_content_hash="a" * 64,
        )
        await SimilarityRunRepository(session).add(run)
        result = TranslationSimilarityResult(
            similarity_run_id=run.id,
            translation_group_id=group_id,
            detected_section_id=section_id,
            source_reference="page:1:block:1",
            source_language_code="id",
            target_language_code="en",
            source_text_hash="b" * 64,
            target_text_hash="c" * 64,
            similarity_score=0.5,
            similarity_category=SimilarityCategory.LOW,
            confidence=0.9,
            analysis_status="COMPLETED",
            source_character_count=30,
            target_character_count=31,
            length_ratio=1.03,
            number_consistency_status=ConsistencyStatus.MISMATCH,
            date_consistency_status=ConsistencyStatus.NOT_APPLICABLE,
            measurement_consistency_status=(
                ConsistencyStatus.NOT_APPLICABLE
            ),
            reference_consistency_status=(
                ConsistencyStatus.NOT_APPLICABLE
            ),
            negation_consistency_status=(
                ConsistencyStatus.NOT_APPLICABLE
            ),
        )
        await TranslationSimilarityRepository(session).add_many([result])
        summary = SectionSimilaritySummary(
            similarity_run_id=run.id,
            detected_section_id=section_id,
            canonical_section_code="PURPOSE",
            total_groups=1,
            eligible_groups=1,
            analysed_groups=1,
            low_similarity_groups=1,
        )
        await SectionSimilarityRepository(session).add_many([summary])
        await session.commit()

        items, total = await TranslationSimilarityRepository(
            session
        ).list_for_run(
            run.id,
            similarity_category=SimilarityCategory.LOW,
            has_number_mismatch=True,
            page=1,
            page_size=100,
        )
        sections, section_total = await SectionSimilarityRepository(
            session
        ).list_for_run(run.id, page=1, page_size=100)
        assert total == 1
        assert items[0].id == result.id
        assert section_total == 1
        assert sections[0].canonical_section_code == "PURPOSE"


@pytest.mark.asyncio
async def test_deterministic_provider_is_stable_and_explicit() -> None:
    provider = DeterministicSimilarityProvider()
    assert await provider.calculate_similarity(
        "the same controlled sentence",
        "the same controlled sentence",
    ) == pytest.approx(1.0)
    first = await provider.encode(["stable text"])
    second = await provider.encode(["stable text"])
    assert first == second
    selected = SimilarityProviderFactory.create(
        SimpleNamespace(similarity_provider="deterministic")
    )
    assert selected.get_provider_info()["testProvider"] is True


@pytest.mark.asyncio
async def test_sentence_provider_never_downloads_missing_model(
    tmp_path: Path,
) -> None:
    provider = SentenceTransformerProvider(
        model_name="missing/private-model",
        model_path=tmp_path,
    )
    assert provider.is_ready() is False
    with pytest.raises(SimilarityProviderUnavailable):
        await provider.encode(["private document text"])


def test_long_text_chunking_is_bounded_and_warns_on_truncation() -> None:
    service = LongTextChunkingService(
        text_max_characters=120,
        chunk_max_characters=50,
        overlap_characters=10,
        maximum_chunks=2,
    )
    result = service.chunk(
        "First sentence. Second sentence. Third sentence. " * 5
    )
    assert len(result.chunks) <= 2
    assert result.complete is False
    assert "SIMILARITY_TEXT_CHARACTER_LIMIT_REACHED" in result.warnings
    assert "SIMILARITY_MAX_CHUNKS_REACHED" in result.warnings
    assert result.original_character_count > result.processed_character_count


@pytest.mark.parametrize(
    ("text", "eligible", "reason"),
    [
        ("", False, "EMPTY_TEXT"),
        ("https://internal.example/document", False, "URL_ONLY_TEXT"),
        ("12345", False, "NUMERIC_ONLY_TEXT"),
        ("SOP-HSE-001", False, "CODE_ONLY_TEXT"),
        ("short", False, "TEXT_TOO_SHORT"),
        ("Install the approved isolation valve.", True, None),
        ("必须关闭隔离阀门并挂牌。", True, None),
    ],
)
def test_text_eligibility_is_conservative(
    text: str, eligible: bool, reason: str | None
) -> None:
    result = TextEligibilityService().evaluate(text)
    assert result.eligible is eligible
    assert result.reason == reason


def test_number_consistency_handles_locale_and_percent() -> None:
    service = NumberConsistencyService()
    assert service.check(
        "Batasnya 1.234,50 dan 10 persen.",
        "The limits are 1,234.50 and 10%.",
    ).status is ConsistencyStatus.MATCH
    mismatch = service.check(
        "Katup ditutup selama 15 hari.",
        "The valve is closed for 30 days.",
    )
    assert mismatch.status is ConsistencyStatus.MISMATCH
    assert mismatch.details["missingInTarget"] == ["15"]


def test_date_consistency_normalizes_languages_and_flags_ambiguity() -> None:
    service = DateConsistencyService()
    result = service.check(
        "Berlaku 25 Juli 2026.",
        "Effective 2026年7月25日.",
    )
    assert result.status is ConsistencyStatus.MATCH
    ambiguous = service.check(
        "Berlaku 03/04/2026.",
        "Effective 2026-04-03.",
    )
    assert ambiguous.status is ConsistencyStatus.AMBIGUOUS
    assert ambiguous.warnings


def test_measurement_reference_and_negation_signals() -> None:
    measurements = MeasurementConsistencyService()
    assert measurements.check(
        "Berat 10 kg.",
        "重量为10千克。",
    ).status is ConsistencyStatus.MATCH
    assert measurements.check(
        "Panjang 10 cm.",
        "Length 10 m.",
    ).status is ConsistencyStatus.MISMATCH
    assert measurements.check(
        "Panjang 100 cm.",
        "Length 1 m.",
    ).status is ConsistencyStatus.POTENTIALLY_EQUIVALENT

    references = ReferenceConsistencyService()
    assert references.check(
        "Lihat Bagian 4.2 dan Tabel 3.",
        "See Section 4.2 and Table 3.",
    ).status is ConsistencyStatus.MATCH
    assert references.check(
        "Lihat Gambar 2.",
        "See Figure 3.",
    ).status is ConsistencyStatus.MISMATCH

    negation = NegationMismatchService()
    signal = negation.check(
        "Pengguna tidak boleh membuka katup.",
        "The user may open the valve.",
        source_language="id",
        target_language="en",
    )
    assert signal.status is ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH


def test_score_categories_and_confidence_are_separate() -> None:
    score = SimilarityScoreService()
    options = SimilarityOptions()
    assert score.category(
        0.90, options.thresholds
    ) is SimilarityCategory.HIGH
    assert score.category(
        0.75, options.thresholds
    ) is SimilarityCategory.ACCEPTABLE
    assert score.category(
        0.60, options.thresholds
    ) is SimilarityCategory.NEEDS_REVIEW
    assert score.category(
        0.40, options.thresholds
    ) is SimilarityCategory.LOW
    confidence = score.confidence(
        group_confidence=0.9,
        source_language_confidence=0.9,
        target_language_confidence=0.9,
        source_characters=100,
        target_characters=100,
        source_chunks_complete=False,
        target_chunks_complete=False,
        source_quality={"ocrConfidence": 0.3},
    )
    assert confidence < 0.8


@pytest.mark.asyncio
async def test_pipeline_runs_all_pairs_and_emits_consistency_findings() -> None:
    context = _context(
        [
            SimilarityMemberData(
                id=uuid4(),
                languageCode="id",
                text="Katup harus ditutup selama 15 hari.",
                confidence=0.95,
            ),
            SimilarityMemberData(
                id=uuid4(),
                languageCode="en",
                text="The valve must remain closed for 30 days.",
                confidence=0.95,
            ),
            SimilarityMemberData(
                id=uuid4(),
                languageCode="zh",
                text="隔离阀门必须保持关闭状态十五天以上。",
                confidence=0.95,
            ),
        ]
    )
    pipeline = TranslationSimilarityService(
        provider=DeterministicSimilarityProvider(),
        chunking=LongTextChunkingService(),
    )
    result = await pipeline.analyse(context)
    assert len(result.results) == 3
    assert result.aggregate.analysed_group_count == 1
    assert any(
        item.number_consistency.status is ConsistencyStatus.MISMATCH
        for item in result.results
    )
    codes = {finding.finding_code for finding in result.findings}
    assert "LOW_TRANSLATION_SIMILARITY" in codes
    assert "TRANSLATION_NUMBER_MISMATCH" in codes
    serialized = result.model_dump(mode="json", by_alias=True)
    assert "sourceText" not in _all_keys(serialized)
    assert "targetText" not in _all_keys(serialized)


@pytest.mark.asyncio
async def test_missing_primary_is_not_a_low_similarity_finding() -> None:
    context = _context(
        [
            SimilarityMemberData(
                languageCode="en",
                text="The approved valve must remain closed.",
                confidence=0.95,
            ),
            SimilarityMemberData(
                languageCode="zh",
                text="经批准的阀门必须保持关闭状态。",
                confidence=0.95,
            ),
        ],
        options=SimilarityOptions(
            primaryLanguage="id",
            requiredPairs=[("id", "en"), ("id", "zh")],
            optionalPairs=[("en", "zh")],
        ),
    )
    pipeline = TranslationSimilarityService(
        provider=DeterministicSimilarityProvider(),
        chunking=LongTextChunkingService(),
    )
    result = await pipeline.analyse(context)
    primary_pairs = [
        item
        for item in result.results
        if "id" in {
            item.source_language_code,
            item.target_language_code,
        }
    ]
    assert all(
        item.similarity_category is SimilarityCategory.NOT_EVALUATED
        for item in primary_pairs
    )
    assert not any(
        finding.finding_code == "LOW_TRANSLATION_SIMILARITY"
        and finding.language_code
        and "id" in finding.language_code
        for finding in result.findings
    )


@pytest.mark.asyncio
async def test_pipeline_honors_cancellation_before_inference() -> None:
    context = _context(
        [
            SimilarityMemberData(
                languageCode="id",
                text="Katup isolasi harus tetap tertutup.",
                confidence=0.9,
            ),
            SimilarityMemberData(
                languageCode="en",
                text="The isolation valve must remain closed.",
                confidence=0.9,
            ),
        ]
    )
    pipeline = TranslationSimilarityService(
        provider=DeterministicSimilarityProvider(),
        chunking=LongTextChunkingService(),
    )

    async def cancelled() -> bool:
        await asyncio.sleep(0)
        return True

    with pytest.raises(SimilarityAnalysisCancelled):
        await pipeline.analyse(context, cancellation_check=cancelled)


def _context(
    members: list[SimilarityMemberData],
    *,
    options: SimilarityOptions | None = None,
) -> SimilarityContext:
    return SimilarityContext(
        documentId=uuid4(),
        documentRevisionId=uuid4(),
        documentFileId=uuid4(),
        complianceRunId=uuid4(),
        languageDetectionRunId=uuid4(),
        sourceContentHash="a" * 64,
        groups=[
            SimilarityGroupData(
                id=uuid4(),
                sourceReference="page:1:block:2",
                groupIndex=0,
                groupType="PARAGRAPH_GROUP",
                confidence=0.95,
                members=members,
                metrics={"isRequiredSection": True},
            )
        ],
        options=options or SimilarityOptions(),
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            *[str(key) for key in value],
            *[
                nested
                for item in value.values()
                for nested in _all_keys(item)
            ],
        }
    if isinstance(value, list):
        return {
            nested
            for item in value
            for nested in _all_keys(item)
        }
    return set()
