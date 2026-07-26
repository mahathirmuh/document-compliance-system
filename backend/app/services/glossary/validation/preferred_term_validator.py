"""Preferred-term glossary validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.glossary.validation._helpers import signal_from_match

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.services.glossary.contracts import (
        GlossaryFindingSignal,
        GlossaryMatchCandidate,
    )


class PreferredTermValidator:
    """Flag non-preferred, non-excepted forms."""

    finding_code = "NON_PREFERRED_GLOSSARY_TERM"

    def validate(
        self,
        matches: Sequence[GlossaryMatchCandidate],
    ) -> list[GlossaryFindingSignal]:
        results: list[GlossaryFindingSignal] = []
        for candidate in matches:
            exception_type = candidate.metadata.get("exceptionType")
            if (
                candidate.is_preferred
                or candidate.is_forbidden
                or candidate.is_allowed_variant
                or exception_type in {"IGNORE_TERM", "ALLOW_VARIANT"}
            ):
                continue
            results.append(
                signal_from_match(
                    candidate,
                    code=self.finding_code,
                    severity=candidate.severity or "MINOR",
                    title="Non-preferred glossary term used",
                    description=(
                        f"'{candidate.matched_text}' is not a preferred form "
                        f"for concept '{candidate.concept_name}'."
                    ),
                    recommendation=(
                        "Review the configured preferred translation and "
                        "update the source through the normal document "
                        "control process if appropriate."
                    ),
                )
            )
        return results
