"""Shared finding construction helpers for glossary validators."""

from __future__ import annotations

from app.services.glossary.contracts import (
    GlossaryFindingSignal,
    GlossaryMatchCandidate,
)


def signal_from_match(
    candidate: GlossaryMatchCandidate,
    *,
    code: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    metrics: dict[str, object] | None = None,
) -> GlossaryFindingSignal:
    return GlossaryFindingSignal(
        finding_code=code,
        severity=severity,
        title=title[:500],
        description=description[:4000],
        recommendation=recommendation[:2000],
        glossary_term_id=candidate.glossary_term_id,
        language_code=candidate.language_code,
        source_reference=candidate.source_reference,
        extracted_block_id=candidate.extracted_block_id,
        ocr_block_id=candidate.ocr_block_id,
        container_id=candidate.container_id,
        detected_section_id=candidate.detected_section_id,
        translation_group_id=candidate.translation_group_id,
        exception_id=candidate.exception_id,
        metrics={
            "termCode": candidate.term_code,
            "conceptName": candidate.concept_name,
            "matchType": candidate.match_type,
            "matchedText": candidate.matched_text[:500],
            "confidence": candidate.confidence,
            **(metrics or {}),
        },
    )
