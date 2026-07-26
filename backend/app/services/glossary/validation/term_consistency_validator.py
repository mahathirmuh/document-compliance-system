"""Document-level glossary translation consistency checks."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from app.services.glossary.contracts import GlossaryFindingSignal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.glossary_term import GlossaryTerm
    from app.services.glossary.contracts import GlossaryMatchCandidate


class TermConsistencyValidator:
    """Flag alternate forms when only one preferred form is configured."""

    finding_code = "INCONSISTENT_GLOSSARY_TRANSLATION"

    def validate(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        terms: Sequence[GlossaryTerm],
    ) -> list[GlossaryFindingSignal]:
        term_by_id = {term.id: term for term in terms}
        grouped: dict[
            tuple[object, str],
            list[GlossaryMatchCandidate],
        ] = defaultdict(list)
        for match in matches:
            if (
                match.is_forbidden
                or match.is_allowed_variant
                or match.metadata.get("exceptionType")
                in {"IGNORE_TERM", "ALLOW_VARIANT"}
            ):
                continue
            grouped[
                (match.glossary_term_id, match.language_code)
            ].append(match)

        findings: list[GlossaryFindingSignal] = []
        for (term_id, language), language_matches in grouped.items():
            term = term_by_id.get(term_id)
            if term is None:
                continue
            preferred_forms = {
                translation.normalised_term
                for translation in term.translations
                if translation.is_active
                and translation.language_code.value == language
                and translation.is_preferred
            }
            if len(preferred_forms) != 1:
                continue
            observed = {
                item.normalised_matched_text for item in language_matches
            }
            if len(observed) <= 1 or observed <= preferred_forms:
                continue
            anchor = next(
                (
                    item
                    for item in language_matches
                    if item.normalised_matched_text not in preferred_forms
                ),
                language_matches[0],
            )
            findings.append(
                GlossaryFindingSignal(
                    finding_code=self.finding_code,
                    severity=term.severity.value,
                    title="Inconsistent glossary translation detected",
                    description=(
                        f"Concept '{term.concept_name}' uses multiple "
                        f"'{language}' forms while one preferred form is "
                        "configured."
                    ),
                    recommendation=(
                        "Review the occurrences and use an approved variant "
                        "or the configured preferred form consistently."
                    ),
                    glossary_term_id=term.id,
                    language_code=language,
                    source_reference=anchor.source_reference,
                    extracted_block_id=anchor.extracted_block_id,
                    ocr_block_id=anchor.ocr_block_id,
                    container_id=anchor.container_id,
                    detected_section_id=anchor.detected_section_id,
                    translation_group_id=anchor.translation_group_id,
                    metrics={
                        "termCode": term.term_code,
                        "observedForms": sorted(observed),
                        "preferredForms": sorted(preferred_forms),
                        "occurrenceCount": len(language_matches),
                    },
                )
            )
        return findings
