"""Forbidden-term glossary validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.glossary.validation._helpers import signal_from_match

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.services.glossary.contracts import (
        GlossaryFindingSignal,
        GlossaryMatchCandidate,
    )


class ForbiddenTermValidator:
    """Flag forbidden terms unless an effective exception applies."""

    finding_code = "FORBIDDEN_GLOSSARY_TERM"

    def validate(
        self,
        matches: Sequence[GlossaryMatchCandidate],
    ) -> list[GlossaryFindingSignal]:
        results: list[GlossaryFindingSignal] = []
        for candidate in matches:
            if not candidate.is_forbidden:
                continue
            if candidate.metadata.get("exceptionType") in {
                "IGNORE_TERM",
                "ALLOW_FORBIDDEN_TERM",
            }:
                continue
            results.append(
                signal_from_match(
                    candidate,
                    code=self.finding_code,
                    severity=candidate.severity,
                    title="Forbidden glossary term detected",
                    description=(
                        f"Forbidden term '{candidate.matched_text}' was "
                        f"detected for concept '{candidate.concept_name}'."
                    ),
                    recommendation=(
                        "Review the wording and use an approved term through "
                        "the controlled document revision process."
                    ),
                )
            )
        return results
