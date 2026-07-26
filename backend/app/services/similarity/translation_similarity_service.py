"""Pure orchestration for multilingual similarity and consistency."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from statistics import fmean
from typing import TypedDict, Unpack
from uuid import UUID

from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
)
from app.schemas.similarity_internal import (
    ConsistencyCheckResult,
    SimilarityContext,
    SimilarityPipelineResult,
    SimilarityResultDraft,
)
from app.services.similarity.alignment.long_text_chunking_service import (
    LongTextChunkingService,
)
from app.services.similarity.alignment.pairwise_language_service import (
    PairCandidate,
    PairwiseLanguageService,
)
from app.services.similarity.alignment.text_eligibility_service import (
    TextEligibilityService,
)
from app.services.similarity.base_similarity_provider import (
    BaseSimilarityProvider,
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
from app.services.similarity.similarity_aggregation_service import (
    SimilarityAggregationService,
)
from app.services.similarity.similarity_finding_service import (
    SimilarityFindingService,
)
from app.services.similarity.similarity_score_service import (
    SimilarityScoreService,
)

CancellationCheck = Callable[[], Awaitable[bool]]
ProgressCallback = Callable[[str, int], Awaitable[None]]


class _SimilarityResultBase(TypedDict):
    translation_group_id: UUID
    detected_section_id: UUID | None
    canonical_section_code: str | None
    container_id: UUID | None
    source_reference: str
    source_language_code: str
    target_language_code: str
    source_member_id: UUID | None
    target_member_id: UUID | None
    source_text_hash: str
    target_text_hash: str


class SimilarityAnalysisCancelled(RuntimeError):
    """Cancellation was observed at a safe pipeline checkpoint."""


class TranslationSimilarityService:
    def __init__(
        self,
        *,
        provider: BaseSimilarityProvider,
        chunking: LongTextChunkingService,
        pairwise: PairwiseLanguageService | None = None,
        score: SimilarityScoreService | None = None,
        aggregation: SimilarityAggregationService | None = None,
        findings: SimilarityFindingService | None = None,
    ) -> None:
        self.provider = provider
        self.chunking = chunking
        self.pairwise = pairwise or PairwiseLanguageService()
        self.score = score or SimilarityScoreService()
        self.aggregation = aggregation or SimilarityAggregationService()
        self.findings = findings or SimilarityFindingService()
        self.numbers = NumberConsistencyService()
        self.dates = DateConsistencyService()
        self.measurements = MeasurementConsistencyService()
        self.references = ReferenceConsistencyService()
        self.negation = NegationMismatchService()

    async def analyse(
        self,
        context: SimilarityContext,
        *,
        cancellation_check: CancellationCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> SimilarityPipelineResult:
        self.score.validate_thresholds(context.options.thresholds)
        eligibility = TextEligibilityService(
            minimum_characters=context.options.minimum_characters,
            skip_code_like_text=context.options.skip_code_like_text,
            skip_numeric_only_text=context.options.skip_numeric_only_text,
        )
        if progress_callback:
            await progress_callback("ALIGNING_GROUPS", 20)
        candidates = [
            (group, pair)
            for group in context.groups
            for pair in self.pairwise.pairs_for_group(
                group, context.options
            )
        ]
        results: list[SimilarityResultDraft] = []
        total = max(1, len(candidates))
        for index, (group, pair) in enumerate(candidates):
            await self._check_cancel(cancellation_check)
            if progress_callback:
                await progress_callback(
                    "ENCODING",
                    35 + int(index * 30 / total),
                )
            result = await self._analyse_pair(
                context,
                group,
                pair,
                eligibility=eligibility,
            )
            results.append(result)
        await self._check_cancel(cancellation_check)
        if progress_callback:
            await progress_callback("CALCULATING_SIMILARITY", 70)
            await progress_callback("CHECKING_CONSISTENCY", 80)
            await progress_callback("AGGREGATING", 88)
        aggregate = self.aggregation.aggregate(context, results)
        sections = self.aggregation.sections(context, results)
        if progress_callback:
            await progress_callback("GENERATING_FINDINGS", 93)
        findings = self.findings.build(
            results,
            thresholds=context.options.thresholds,
        )
        warnings = [
            *context.warnings,
            *[
                warning
                for result in results
                for warning in result.warnings
            ],
        ]
        return SimilarityPipelineResult(
            context=context,
            results=results,
            section_summaries=sections,
            findings=findings,
            aggregate=aggregate,
            provider_info=self.provider.get_provider_info(),
            warnings=list(dict.fromkeys(warnings)),
        )

    async def _analyse_pair(
        self,
        context: SimilarityContext,
        group,
        pair: PairCandidate,
        *,
        eligibility: TextEligibilityService,
    ) -> SimilarityResultDraft:
        source_text = pair.source.text if pair.source else ""
        target_text = pair.target.text if pair.target else ""
        source_hash = _text_hash(source_text)
        target_hash = _text_hash(target_text)
        base: _SimilarityResultBase = {
            "translation_group_id": group.id,
            "detected_section_id": group.detected_section_id,
            "canonical_section_code": group.canonical_section_code,
            "container_id": group.container_id,
            "source_reference": group.source_reference,
            "source_language_code": pair.source_language,
            "target_language_code": pair.target_language,
            "source_member_id": pair.source.member_id if pair.source else None,
            "target_member_id": pair.target.member_id if pair.target else None,
            "source_text_hash": source_hash,
            "target_text_hash": target_hash,
        }
        if (
            group.confidence
            < context.options.minimum_group_confidence
        ):
            return self._not_evaluated(
                **base,
                status=SimilarityAnalysisStatus.INSUFFICIENT_CONTENT,
                reason="GROUP_CONFIDENCE_TOO_LOW",
                source_text=source_text,
                target_text=target_text,
                confidence=group.confidence,
                required=pair.required,
                group_confidence=group.confidence,
            )
        if pair.source is None or pair.target is None:
            return self._not_evaluated(
                **base,
                status=SimilarityAnalysisStatus.INSUFFICIENT_CONTENT,
                reason=(
                    "PRIMARY_LANGUAGE_MISSING"
                    if pair.missing_primary_language
                    else "PAIR_LANGUAGE_MISSING"
                ),
                source_text=source_text,
                target_text=target_text,
                confidence=0,
                required=pair.required,
                group_confidence=group.confidence,
            )
        source_eligibility = eligibility.evaluate(source_text)
        target_eligibility = eligibility.evaluate(target_text)
        if not source_eligibility.eligible or not target_eligibility.eligible:
            selected = (
                source_eligibility
                if not source_eligibility.eligible
                else target_eligibility
            )
            return self._not_evaluated(
                **base,
                status=selected.status,
                reason=selected.reason or "PAIR_NOT_ELIGIBLE",
                source_text=source_eligibility.normalized_text,
                target_text=target_eligibility.normalized_text,
                confidence=min(pair.source.confidence, pair.target.confidence),
                required=pair.required,
                group_confidence=group.confidence,
            )
        source_chunks = self.chunking.chunk(
            source_eligibility.normalized_text
        )
        target_chunks = self.chunking.chunk(
            target_eligibility.normalized_text
        )
        embeddings = await self.provider.encode(
            [
                *[item.text for item in source_chunks.chunks],
                *[item.text for item in target_chunks.chunks],
            ]
        )
        split = len(source_chunks.chunks)
        source_embedding = _mean_embedding(embeddings[:split])
        target_embedding = _mean_embedding(embeddings[split:])
        similarity = self.provider.cosine_similarity(
            source_embedding, target_embedding
        )
        source_quality = dict(context.source_quality)
        pair_ocr_confidences = [
            value
            for value in (
                pair.source.ocr_confidence,
                pair.target.ocr_confidence,
            )
            if value is not None
        ]
        if pair_ocr_confidences:
            source_quality["ocrConfidence"] = min(
                pair_ocr_confidences
            )
        confidence = self.score.confidence(
            group_confidence=group.confidence,
            source_language_confidence=pair.source.confidence,
            target_language_confidence=pair.target.confidence,
            source_characters=source_eligibility.character_count,
            target_characters=target_eligibility.character_count,
            source_chunks_complete=source_chunks.complete,
            target_chunks_complete=target_chunks.complete,
            source_quality=source_quality,
        )
        ratio = self.score.length_ratio(
            source_eligibility.normalized_text,
            target_eligibility.normalized_text,
        )
        length_anomaly, length_range = (
            self.score.length_ratio_is_anomalous(
                ratio,
                source_language=pair.source_language,
                target_language=pair.target_language,
                configured=context.options.length_ratio_ranges,
            )
        )
        number = self.numbers.check(source_text, target_text)
        date = self.dates.check(source_text, target_text)
        measurement = self.measurements.check(source_text, target_text)
        reference = self.references.check(source_text, target_text)
        negation = self.negation.check(
            source_text,
            target_text,
            source_language=pair.source_language,
            target_language=pair.target_language,
        )
        return SimilarityResultDraft(
            **base,
            similarity_score=round(similarity, 6),
            similarity_category=self.score.category(
                similarity, context.options.thresholds
            ),
            confidence=confidence,
            analysis_status=SimilarityAnalysisStatus.COMPLETED,
            source_character_count=source_eligibility.character_count,
            target_character_count=target_eligibility.character_count,
            length_ratio=round(ratio, 6) if ratio is not None else None,
            number_consistency=number,
            date_consistency=date,
            measurement_consistency=measurement,
            reference_consistency=reference,
            negation_consistency=negation,
            chunk_count_source=len(source_chunks.chunks),
            chunk_count_target=len(target_chunks.chunks),
            metrics={
                "requiredPair": pair.required,
                "requiredSection": bool(
                    group.metrics.get("isRequiredSection")
                ),
                "groupConfidence": group.confidence,
                "sourceLanguageConfidence": pair.source.confidence,
                "targetLanguageConfidence": pair.target.confidence,
                "ocrConfidence": source_quality.get("ocrConfidence"),
                "lengthRatioAnomaly": length_anomaly,
                "lengthRatioRange": (
                    list(length_range) if length_range else None
                ),
                "sourceChunksComplete": source_chunks.complete,
                "targetChunksComplete": target_chunks.complete,
                "sourceChunkMetadata": [
                    {
                        "index": chunk.index,
                        "startCharacter": chunk.start_character,
                        "endCharacter": chunk.end_character,
                    }
                    for chunk in source_chunks.chunks
                ],
                "targetChunkMetadata": [
                    {
                        "index": chunk.index,
                        "startCharacter": chunk.start_character,
                        "endCharacter": chunk.end_character,
                    }
                    for chunk in target_chunks.chunks
                ],
                "sourceProcessedCharacters": (
                    source_chunks.processed_character_count
                ),
                "targetProcessedCharacters": (
                    target_chunks.processed_character_count
                ),
            },
            warnings=[
                *source_chunks.warnings,
                *target_chunks.warnings,
                *date.warnings,
            ],
        )

    def _not_evaluated(
        self,
        *,
        status: SimilarityAnalysisStatus,
        reason: str,
        source_text: str,
        target_text: str,
        confidence: float,
        required: bool,
        group_confidence: float,
        **base: Unpack[_SimilarityResultBase],
    ) -> SimilarityResultDraft:
        not_applicable = ConsistencyCheckResult(
            status=ConsistencyStatus.NOT_APPLICABLE,
        )
        return SimilarityResultDraft(
            **base,
            similarity_score=None,
            similarity_category=SimilarityCategory.NOT_EVALUATED,
            confidence=max(0.0, min(1.0, confidence)),
            analysis_status=status,
            source_character_count=len(source_text),
            target_character_count=len(target_text),
            length_ratio=self.score.length_ratio(
                source_text, target_text
            ),
            number_consistency=not_applicable,
            date_consistency=not_applicable,
            measurement_consistency=not_applicable,
            reference_consistency=not_applicable,
            negation_consistency=not_applicable,
            metrics={
                "eligibilityReason": reason,
                "requiredPair": required,
                "groupConfidence": group_confidence,
            },
            warnings=[reason],
        )

    @staticmethod
    async def _check_cancel(
        callback: CancellationCheck | None,
    ) -> None:
        if callback is not None and await callback():
            raise SimilarityAnalysisCancelled(
                "Similarity analysis was cancelled."
            )


def _text_hash(text: str) -> str:
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _mean_embedding(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    width = len(embeddings[0])
    if any(len(item) != width for item in embeddings):
        return []
    return [
        fmean(item[index] for item in embeddings)
        for index in range(width)
    ]
