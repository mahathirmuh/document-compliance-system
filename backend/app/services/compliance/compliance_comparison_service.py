"""Pure comparison of two retained compliance run snapshots."""

from __future__ import annotations

from app.services.compliance._compat import (
    enum_value,
    first,
    float_value,
    read,
    sequence,
    string_list,
)
from app.services.compliance.contracts import ComparisonResult
from app.services.compliance.findings.finding_deduplication_service import (
    FindingDeduplicationService,
)


class ComplianceComparisonService:
    """Report changes only; finding statuses are never mutated."""

    def __init__(
        self,
        deduplication: FindingDeduplicationService | None = None,
    ) -> None:
        self.deduplication = (
            deduplication or FindingDeduplicationService()
        )

    def compare(
        self,
        previous: object,
        current: object,
    ) -> ComparisonResult:
        previous_score = float_value(
            first(
                previous,
                "compliance_score",
                "score",
                default=0.0,
            ),
        )
        current_score = float_value(
            first(
                current,
                "compliance_score",
                "score",
                default=0.0,
            ),
        )
        previous_languages = set(self._languages(previous))
        current_languages = set(self._languages(current))
        previous_sections = set(self._sections(previous))
        current_sections = set(self._sections(current))
        previous_findings = sequence(read(previous, "findings", []))
        current_findings = sequence(read(current, "findings", []))
        new, not_reproduced, repeated = self.deduplication.compare(
            current_findings,
            previous_findings,
        )
        previous_complete, previous_total = self._group_counts(previous)
        current_complete, current_total = self._group_counts(current)
        return ComparisonResult(
            score_change=round(current_score - previous_score, 4),
            previous_status=enum_value(
                first(
                    previous,
                    "compliance_status",
                    "status",
                    default="NOT_EVALUATED",
                ),
            ),
            current_status=enum_value(
                first(
                    current,
                    "compliance_status",
                    "status",
                    default="NOT_EVALUATED",
                ),
            ),
            languages_added=tuple(
                sorted(current_languages - previous_languages),
            ),
            languages_removed=tuple(
                sorted(previous_languages - current_languages),
            ),
            sections_added=tuple(
                sorted(current_sections - previous_sections),
            ),
            sections_removed=tuple(
                sorted(previous_sections - current_sections),
            ),
            new_findings=tuple(new),
            not_reproduced_findings=tuple(not_reproduced),
            repeated_findings=tuple(repeated),
            translation_group_complete_change=(
                current_complete - previous_complete
            ),
            metrics={
                "previousTranslationGroups": {
                    "total": previous_total,
                    "complete": previous_complete,
                },
                "currentTranslationGroups": {
                    "total": current_total,
                    "complete": current_complete,
                },
                "findingStatusesMutated": False,
            },
        )

    @staticmethod
    def _languages(run: object) -> list[str]:
        explicit = first(
            run,
            "detected_languages",
            "detected_languages_json",
            default=None,
        )
        if explicit is not None:
            return string_list(explicit)
        presence = read(run, "language_presence", {})
        return [
            str(language)
            for language, status in (
                presence.items() if isinstance(presence, dict) else []
            )
            if enum_value(status).upper() == "PRESENT"
        ]

    @staticmethod
    def _sections(run: object) -> list[str]:
        explicit = first(
            run,
            "detected_sections",
            "detected_sections_json",
            default=None,
        )
        if explicit is not None:
            values = sequence(explicit)
            return [
                enum_value(
                    first(
                        value,
                        "canonical_code",
                        default=value,
                    ),
                )
                for value in values
            ]
        sections = sequence(read(run, "sections", []))
        return [
            enum_value(read(section, "canonical_code", ""))
            for section in sections
        ]

    @staticmethod
    def _group_counts(run: object) -> tuple[int, int]:
        raw_groups = read(run, "translation_groups", [])
        if isinstance(raw_groups, dict):
            return (
                int(raw_groups.get("complete", 0)),
                int(raw_groups.get("total", 0)),
            )
        groups = sequence(raw_groups)
        return (
            sum(bool(read(group, "is_complete", False)) for group in groups),
            len(groups),
        )

