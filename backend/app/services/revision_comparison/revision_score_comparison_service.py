"""Classify independent quality deltas without rewriting Phase 8 scores."""

from __future__ import annotations

from app.models.revision_comparison import RevisionComparisonClassification


class RevisionScoreComparisonService:
    def classify(
        self,
        *,
        compliance_delta: float | None,
        similarity_delta: float | None,
        glossary_violation_delta: int | None,
        open_finding_delta: int | None,
        critical_finding_delta: int | None = None,
        tolerance: float = 0.001,
    ) -> RevisionComparisonClassification:
        directions: list[int] = []
        for delta in (compliance_delta, similarity_delta):
            if delta is None or abs(delta) <= tolerance:
                continue
            directions.append(1 if delta > 0 else -1)
        for delta in (
            glossary_violation_delta,
            open_finding_delta,
            critical_finding_delta,
        ):
            if delta is None or delta == 0:
                continue
            directions.append(1 if delta < 0 else -1)
        if not directions:
            return RevisionComparisonClassification.UNCHANGED
        if all(direction > 0 for direction in directions):
            return RevisionComparisonClassification.IMPROVED
        if all(direction < 0 for direction in directions):
            return RevisionComparisonClassification.REGRESSED
        return RevisionComparisonClassification.MIXED
