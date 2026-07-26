"""Threshold categorization, length ratios, and evidence confidence."""

from __future__ import annotations

from app.models.similarity_enums import SimilarityCategory
from app.schemas.similarity_internal import SimilarityThresholds

_DEFAULT_LENGTH_RANGES: dict[str, tuple[float, float]] = {
    "id-en": (0.55, 1.80),
    "id-zh": (0.20, 1.10),
    "en-zh": (0.20, 1.10),
}


class SimilarityScoreService:
    @staticmethod
    def validate_thresholds(thresholds: SimilarityThresholds) -> None:
        if not (
            thresholds.high
            >= thresholds.acceptable
            >= thresholds.review
            >= thresholds.critical_low
        ):
            raise ValueError(
                "Similarity thresholds must be descending from high to "
                "critical-low."
            )

    def category(
        self,
        score: float | None,
        thresholds: SimilarityThresholds,
    ) -> SimilarityCategory:
        self.validate_thresholds(thresholds)
        if score is None:
            return SimilarityCategory.NOT_EVALUATED
        bounded = max(0.0, min(1.0, score))
        if bounded >= thresholds.high:
            return SimilarityCategory.HIGH
        if bounded >= thresholds.acceptable:
            return SimilarityCategory.ACCEPTABLE
        if bounded >= thresholds.review:
            return SimilarityCategory.NEEDS_REVIEW
        return SimilarityCategory.LOW

    @staticmethod
    def length_ratio(
        source_text: str,
        target_text: str,
    ) -> float | None:
        source_count = len(source_text)
        return (
            len(target_text) / source_count
            if source_count
            else None
        )

    def length_ratio_is_anomalous(
        self,
        ratio: float | None,
        *,
        source_language: str,
        target_language: str,
        configured: dict[str, dict[str, float]],
    ) -> tuple[bool, tuple[float, float] | None]:
        if ratio is None:
            return False, None
        pair = f"{source_language.casefold()}-{target_language.casefold()}"
        values = configured.get(pair, {})
        default = _DEFAULT_LENGTH_RANGES.get(pair, (0.35, 2.50))
        minimum = float(values.get("minimum", default[0]))
        maximum = float(values.get("maximum", default[1]))
        if minimum < 0 or maximum <= minimum:
            minimum, maximum = default
        return ratio < minimum or ratio > maximum, (minimum, maximum)

    @staticmethod
    def confidence(
        *,
        group_confidence: float,
        source_language_confidence: float,
        target_language_confidence: float,
        source_characters: int,
        target_characters: int,
        source_chunks_complete: bool,
        target_chunks_complete: bool,
        source_quality: dict[str, float | bool | None],
    ) -> float:
        group = _bounded(group_confidence)
        language = _bounded(
            (source_language_confidence + target_language_confidence) / 2
        )
        shortest = min(source_characters, target_characters)
        text = min(1.0, shortest / 100)
        chunks = (
            float(source_chunks_complete)
            + float(target_chunks_complete)
        ) / 2
        extraction_value = source_quality.get("extractionConfidence")
        extraction = (
            _bounded(float(extraction_value))
            if extraction_value is not None
            else 1.0
        )
        ocr_value = source_quality.get("ocrConfidence")
        ocr = _bounded(float(ocr_value)) if ocr_value is not None else 1.0
        quality = min(extraction, ocr)
        value = (
            group * 0.30
            + language * 0.25
            + text * 0.15
            + chunks * 0.15
            + quality * 0.15
        )
        return round(_bounded(value), 6)


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
