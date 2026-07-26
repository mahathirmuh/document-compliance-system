"""Glossary match and finding coverage metrics."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.services.glossary.contracts import (
        GlossaryFindingSignal,
        GlossaryMatchCandidate,
    )


class GlossaryCoverageValidator:
    """Summarize coverage without claiming linguistic correctness."""

    @staticmethod
    def metrics(
        *,
        total_terms: int,
        matches: Sequence[GlossaryMatchCandidate],
        findings: Sequence[GlossaryFindingSignal],
    ) -> dict[str, object]:
        matched_term_ids = {item.glossary_term_id for item in matches}
        language_counts = Counter(item.language_code for item in matches)
        finding_counts = Counter(item.finding_code for item in findings)
        return {
            "totalTerms": total_terms,
            "matchedConcepts": len(matched_term_ids),
            "unmatchedConcepts": max(0, total_terms - len(matched_term_ids)),
            "conceptCoveragePercentage": (
                round(len(matched_term_ids) / total_terms * 100, 2)
                if total_terms
                else 0.0
            ),
            "languageCounts": dict(language_counts),
            "findingCounts": dict(finding_counts),
            "disclaimer": (
                "Glossary matching is a review signal and does not prove "
                "translation correctness."
            ),
        }
