"""Required glossary concept presence validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.glossary_enums import GlossaryTermType
from app.services.glossary.contracts import GlossaryFindingSignal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.glossary_term import GlossaryTerm
    from app.services.glossary.contracts import GlossaryMatchCandidate


class RequiredTermValidator:
    """Flag required concepts absent from all eligible blocks."""

    finding_code = "REQUIRED_GLOSSARY_TERM_MISSING"

    def validate(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        terms: Sequence[GlossaryTerm],
        *,
        excepted_term_ids: set[object] | None = None,
    ) -> list[GlossaryFindingSignal]:
        excepted_term_ids = excepted_term_ids or set()
        present = {item.glossary_term_id for item in matches}
        return [
            GlossaryFindingSignal(
                finding_code=self.finding_code,
                severity=term.severity.value,
                title="Required glossary concept is missing",
                description=(
                    f"Required concept '{term.concept_name}' was not found "
                    "in eligible extracted content."
                ),
                recommendation=(
                    "Review document applicability and add the approved "
                    "concept through the controlled revision process."
                ),
                glossary_term_id=term.id,
                metrics={"termCode": term.term_code},
            )
            for term in terms
            if term.is_active
            and term.term_type is GlossaryTermType.REQUIRED
            and term.id not in present
            and term.id not in excepted_term_ids
        ]
