"""Language-aware change summaries for Indonesian, English, and Chinese."""

from __future__ import annotations

from collections import Counter

from app.models.revision_change import RevisionChangeType
from app.services.revision_comparison.revision_change_detection_service import (
    DetectedRevisionChange,
)

SUPPORTED_REVISION_LANGUAGES = ("id", "en", "zh")


class RevisionLanguageComparisonService:
    def summarize(
        self,
        changes: list[DetectedRevisionChange],
        *,
        base_language_counts: dict[str, int] | None = None,
        target_language_counts: dict[str, int] | None = None,
        base_language_coverage: dict[str, float] | None = None,
        target_language_coverage: dict[str, float] | None = None,
    ) -> list[dict[str, object]]:
        base_counts = Counter(base_language_counts or {})
        target_counts = Counter(target_language_counts or {})
        additions: Counter[str] = Counter()
        removals: Counter[str] = Counter()
        modifications: Counter[str] = Counter()
        for change in changes:
            language = (
                change.language_code
                if change.language_code in SUPPORTED_REVISION_LANGUAGES
                else "unknown"
            )
            if change.change_type is RevisionChangeType.ADDED:
                additions[language] += 1
            elif change.change_type is RevisionChangeType.REMOVED:
                removals[language] += 1
            elif change.change_type in {
                RevisionChangeType.MODIFIED,
                RevisionChangeType.MOVED,
                RevisionChangeType.SPLIT,
                RevisionChangeType.MERGED,
            }:
                modifications[language] += 1

        if base_language_counts is None:
            for language in (*SUPPORTED_REVISION_LANGUAGES, "unknown"):
                base_counts[language] = max(
                    0,
                    target_counts[language]
                    + removals[language]
                    - additions[language],
                )
        if target_language_counts is None:
            for language in (*SUPPORTED_REVISION_LANGUAGES, "unknown"):
                target_counts[language] = max(
                    0,
                    base_counts[language]
                    + additions[language]
                    - removals[language],
                )

        result: list[dict[str, object]] = []
        for language in SUPPORTED_REVISION_LANGUAGES:
            base_presence = base_counts[language] > 0
            target_presence = target_counts[language] > 0
            base_coverage = self._coverage(
                base_language_coverage, language
            )
            target_coverage = self._coverage(
                target_language_coverage, language
            )
            result.append(
                {
                    "languageCode": language,
                    "baseCount": base_counts[language],
                    "targetCount": target_counts[language],
                    "baseCoverage": base_coverage,
                    "targetCoverage": target_coverage,
                    "coverageChange": (
                        round(target_coverage - base_coverage, 2)
                        if base_coverage is not None
                        and target_coverage is not None
                        else None
                    ),
                    "additions": additions[language],
                    "removals": removals[language],
                    "modifications": modifications[language],
                    "basePresence": base_presence,
                    "targetPresence": target_presence,
                    "regression": base_presence and not target_presence,
                    "fixedMissingLanguage": (
                        not base_presence and target_presence
                    ),
                }
            )
        return result

    @staticmethod
    def _coverage(
        values: dict[str, float] | None, language: str
    ) -> float | None:
        if values is None or language not in values:
            return None
        value = float(values[language])
        return value if 0 <= value <= 100 else None
