"""Translation-group-aware required glossary translation validation."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from app.services.glossary.contracts import GlossaryFindingSignal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.glossary_term import GlossaryTerm
    from app.services.glossary.contracts import GlossaryMatchCandidate


class RequiredTranslationValidator:
    """Require configured languages in the same Phase 8 context."""

    finding_code = "MISSING_GLOSSARY_TRANSLATION"

    def validate(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        terms: Sequence[GlossaryTerm],
        *,
        excepted: set[tuple[object, str, str]] | None = None,
    ) -> list[GlossaryFindingSignal]:
        excepted = excepted or set()
        term_by_id = {term.id: term for term in terms}
        grouped: dict[
            tuple[object, str],
            list[GlossaryMatchCandidate],
        ] = defaultdict(list)
        for match in matches:
            if match.metadata.get("exceptionType") == "IGNORE_TERM":
                continue
            grouped[(match.glossary_term_id, match.context_key)].append(match)

        findings: list[GlossaryFindingSignal] = []
        for (term_id, context_key), context_matches in grouped.items():
            term = term_by_id.get(term_id)
            if term is None:
                continue
            required_languages = {
                translation.language_code.value
                for translation in term.translations
                if translation.is_active and translation.is_required
            }
            present_languages = {
                match.language_code for match in context_matches
            }
            anchor = context_matches[0]
            for language in sorted(required_languages - present_languages):
                if (term_id, context_key, language) in excepted:
                    continue
                findings.append(
                    GlossaryFindingSignal(
                        finding_code=self.finding_code,
                        severity=term.severity.value,
                        title="Required glossary translation is missing",
                        description=(
                            f"Concept '{term.concept_name}' is present in "
                            f"context '{context_key}' but its required "
                            f"'{language}' translation is missing."
                        ),
                        recommendation=(
                            "Review the same translation group and add the "
                            "approved language form when required."
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
                            "contextKey": context_key,
                            "presentLanguages": sorted(present_languages),
                            "requiredLanguage": language,
                            "groupScoped": (
                                anchor.translation_group_id is not None
                            ),
                        },
                    )
                )
        return findings
