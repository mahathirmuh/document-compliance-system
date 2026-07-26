"""Explicit, non-destructive Phase 9 document quality scoring."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models.validation_rule import QualityScoreMode


class QualityStatus(StrEnum):
    """Quality terminology kept separate from compliance status."""

    HIGH_QUALITY = "HIGH_QUALITY"
    ACCEPTABLE = "ACCEPTABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    LOW_QUALITY = "LOW_QUALITY"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class QualityScoreResult:
    """One bounded score and its quality-specific status."""

    score: float | None
    status: QualityStatus


class QualityScoreService:
    """Calculate quality scores without mutating historical compliance data."""

    @staticmethod
    def translation_quality(
        average_similarity: float | None,
    ) -> QualityScoreResult:
        if average_similarity is None:
            return QualityScoreResult(
                score=None,
                status=QualityStatus.NOT_EVALUATED,
            )
        score = QualityScoreService._bounded(
            float(average_similarity) * 100
        )
        return QualityScoreResult(
            score=score,
            status=QualityScoreService.status_for(score),
        )

    @staticmethod
    def glossary_quality(
        *,
        total_terms: int,
        forbidden_terms: int,
        missing_translations: int,
        inconsistent_terms: int,
    ) -> QualityScoreResult:
        if total_terms <= 0:
            return QualityScoreResult(
                score=None,
                status=QualityStatus.NOT_EVALUATED,
            )
        violations = max(
            0,
            forbidden_terms
            + missing_translations
            + inconsistent_terms,
        )
        score = QualityScoreService._bounded(
            100 * (1 - (violations / total_terms))
        )
        return QualityScoreResult(
            score=score,
            status=QualityScoreService.status_for(score),
        )

    @staticmethod
    def combined_score(
        *,
        structural_score: float,
        translation_score: float | None,
        glossary_score: float | None,
        mode: QualityScoreMode | str,
        translation_weight: float,
        glossary_weight: float,
        target: QualityScoreMode,
    ) -> QualityScoreResult:
        """Return a configured composite only for the explicitly named target."""

        selected_mode = QualityScoreService._mode(mode)
        if selected_mode is not target:
            return QualityScoreResult(
                score=None,
                status=QualityStatus.NOT_EVALUATED,
            )
        translation_weight = QualityScoreService._weight(
            translation_weight
        )
        glossary_weight = QualityScoreService._weight(glossary_weight)
        if translation_weight + glossary_weight > 100:
            raise ValueError("Phase 9 quality weights must total 100 or less.")
        if translation_weight > 0 and translation_score is None:
            return QualityScoreResult(
                score=None,
                status=QualityStatus.NOT_EVALUATED,
            )
        if glossary_weight > 0 and glossary_score is None:
            return QualityScoreResult(
                score=None,
                status=QualityStatus.NOT_EVALUATED,
            )
        structural_weight = 100 - translation_weight - glossary_weight
        score = (
            QualityScoreService._bounded(structural_score)
            * structural_weight
            + QualityScoreService._bounded(translation_score or 0)
            * translation_weight
            + QualityScoreService._bounded(glossary_score or 0)
            * glossary_weight
        ) / 100
        bounded = QualityScoreService._bounded(score)
        return QualityScoreResult(
            score=bounded,
            status=QualityScoreService.status_for(bounded),
        )

    @staticmethod
    def configuration_snapshot(
        *,
        mode: QualityScoreMode | str,
        translation_weight: float,
        glossary_weight: float,
    ) -> dict[str, Any]:
        """Return the immutable configuration recorded with Phase 9 results."""

        selected_mode = QualityScoreService._mode(mode)
        translation = QualityScoreService._weight(translation_weight)
        glossary = QualityScoreService._weight(glossary_weight)
        if translation + glossary > 100:
            raise ValueError("Phase 9 quality weights must total 100 or less.")
        return {
            "version": "phase9-v1",
            "mode": selected_mode.value,
            "structuralComplianceWeight": 100 - translation - glossary,
            "translationSimilarityWeight": translation,
            "glossaryComplianceWeight": glossary,
            "preservesHistoricalComplianceScore": True,
            "preservesComplianceStatus": True,
        }

    @staticmethod
    def configuration_from_rule_snapshot(
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Read both API and persistence aliases from a retained rule."""

        mode = snapshot.get(
            "qualityScoreMode",
            snapshot.get(
                "quality_score_mode",
                QualityScoreMode.SEPARATE_QUALITY_SCORE.value,
            ),
        )
        translation_weight = snapshot.get(
            "translationSimilarityWeight",
            snapshot.get("translation_similarity_weight", 25),
        )
        glossary_weight = snapshot.get(
            "glossaryComplianceWeight",
            snapshot.get("glossary_compliance_weight", 15),
        )
        return QualityScoreService.configuration_snapshot(
            mode=str(mode),
            translation_weight=float(translation_weight),
            glossary_weight=float(glossary_weight),
        )

    @staticmethod
    def status_for(score: float | None) -> QualityStatus:
        if score is None:
            return QualityStatus.NOT_EVALUATED
        bounded = QualityScoreService._bounded(score)
        if bounded >= 85:
            return QualityStatus.HIGH_QUALITY
        if bounded >= 72:
            return QualityStatus.ACCEPTABLE
        if bounded >= 58:
            return QualityStatus.NEEDS_REVIEW
        return QualityStatus.LOW_QUALITY

    @staticmethod
    def _bounded(value: float) -> float:
        return round(min(100.0, max(0.0, float(value))), 2)

    @staticmethod
    def _weight(value: float) -> float:
        numeric = float(value)
        if not 0 <= numeric <= 100:
            raise ValueError("A Phase 9 quality weight must be 0 to 100.")
        return numeric

    @staticmethod
    def _mode(value: QualityScoreMode | str) -> QualityScoreMode:
        try:
            return QualityScoreMode(value)
        except ValueError as exc:
            raise ValueError("Unsupported Phase 9 quality score mode.") from exc
