"""Phase 9 quality-score separation and snapshot tests."""

import pytest

from app.models.validation_rule import QualityScoreMode
from app.services.quality_score_service import (
    QualityScoreService,
    QualityStatus,
)


def test_translation_and_glossary_quality_use_quality_statuses() -> None:
    translation = QualityScoreService.translation_quality(0.91)
    glossary = QualityScoreService.glossary_quality(
        total_terms=20,
        forbidden_terms=1,
        missing_translations=1,
        inconsistent_terms=0,
    )

    assert translation.score == 91
    assert translation.status is QualityStatus.HIGH_QUALITY
    assert glossary.score == 90
    assert glossary.status is QualityStatus.HIGH_QUALITY


def test_separate_mode_does_not_create_a_composite_score() -> None:
    result = QualityScoreService.combined_score(
        structural_score=96,
        translation_score=80,
        glossary_score=70,
        mode=QualityScoreMode.SEPARATE_QUALITY_SCORE,
        translation_weight=25,
        glossary_weight=15,
        target=QualityScoreMode.INCLUDE_IN_COMPLIANCE_SCORE,
    )

    assert result.score is None
    assert result.status is QualityStatus.NOT_EVALUATED


def test_overall_quality_requires_explicit_mode_and_all_components() -> None:
    result = QualityScoreService.combined_score(
        structural_score=90,
        translation_score=80,
        glossary_score=70,
        mode=QualityScoreMode.INCLUDE_IN_OVERALL_QUALITY_SCORE,
        translation_weight=25,
        glossary_weight=15,
        target=QualityScoreMode.INCLUDE_IN_OVERALL_QUALITY_SCORE,
    )

    assert result.score == 84.5
    assert result.status is QualityStatus.ACCEPTABLE


def test_configuration_snapshot_preserves_compliance_history() -> None:
    snapshot = QualityScoreService.configuration_snapshot(
        mode=QualityScoreMode.SEPARATE_QUALITY_SCORE,
        translation_weight=25,
        glossary_weight=15,
    )

    assert snapshot == {
        "version": "phase9-v1",
        "mode": "SEPARATE_QUALITY_SCORE",
        "structuralComplianceWeight": 60.0,
        "translationSimilarityWeight": 25.0,
        "glossaryComplianceWeight": 15.0,
        "preservesHistoricalComplianceScore": True,
        "preservesComplianceStatus": True,
    }


def test_invalid_quality_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="total 100 or less"):
        QualityScoreService.configuration_snapshot(
            mode=QualityScoreMode.SEPARATE_QUALITY_SCORE,
            translation_weight=75,
            glossary_weight=30,
        )

