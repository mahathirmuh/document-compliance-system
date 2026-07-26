"""Pure local glossary validation over extracted Phase 6/7/8 content."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from app.models.glossary_enums import GlossaryExceptionType
from app.services.glossary.contracts import (
    GlossaryFindingSignal,
    GlossaryMatchCandidate,
    GlossaryTextBlock,
    GlossaryValidationResult,
    GlossaryValidationScope,
)
from app.services.glossary.glossary_exception_service import (
    GlossaryExceptionService,
)
from app.services.glossary.glossary_matching_service import (
    GlossaryMatchingService,
)
from app.services.glossary.validation.forbidden_term_validator import (
    ForbiddenTermValidator,
)
from app.services.glossary.validation.glossary_coverage_validator import (
    GlossaryCoverageValidator,
)
from app.services.glossary.validation.preferred_term_validator import (
    PreferredTermValidator,
)
from app.services.glossary.validation.required_term_validator import (
    RequiredTermValidator,
)
from app.services.glossary.validation.required_translation_validator import (
    RequiredTranslationValidator,
)
from app.services.glossary.validation.term_consistency_validator import (
    TermConsistencyValidator,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.glossary_exception import GlossaryException
    from app.models.glossary_term import GlossaryTerm


class GlossaryValidationService:
    """Orchestrate matchers, exceptions, and non-destructive review signals."""

    def __init__(
        self,
        matching: GlossaryMatchingService | None = None,
    ) -> None:
        self.matching = matching or GlossaryMatchingService()
        self.exceptions = GlossaryExceptionService()
        self.preferred = PreferredTermValidator()
        self.forbidden = ForbiddenTermValidator()
        self.required_translation = RequiredTranslationValidator()
        self.required_term = RequiredTermValidator()
        self.consistency = TermConsistencyValidator()
        self.coverage = GlossaryCoverageValidator()

    def validate(
        self,
        *,
        blocks: Sequence[GlossaryTextBlock],
        terms: Sequence[GlossaryTerm],
        exceptions: Sequence[GlossaryException] = (),
        scope: GlossaryValidationScope | None = None,
        as_of: date | None = None,
    ) -> GlossaryValidationResult:
        effective_scope = scope or GlossaryValidationScope()
        effective_date = as_of or datetime.now(UTC).date()
        matches, warnings = self.matching.match(blocks, terms)
        language_mismatches = self.matching.detect_language_mismatches(
            blocks,
            terms,
        )
        matches, expired_signals = self._apply_match_exceptions(
            matches,
            exceptions,
            scope=effective_scope,
            as_of=effective_date,
        )
        translation_excepted, expired_translation = (
            self._required_translation_exceptions(
                matches,
                terms,
                exceptions,
                scope=effective_scope,
                as_of=effective_date,
            )
        )
        required_term_excepted, expired_required = (
            self._required_term_exceptions(
                matches,
                terms,
                exceptions,
                scope=effective_scope,
                as_of=effective_date,
            )
        )

        findings = [
            *self.preferred.validate(matches),
            *self.forbidden.validate(matches),
            *self.required_translation.validate(
                matches,
                terms,
                excepted=translation_excepted,
            ),
            *self.required_term.validate(
                matches,
                terms,
                excepted_term_ids=required_term_excepted,
            ),
            *self.consistency.validate(matches, terms),
            *self._language_mismatch_findings(
                language_mismatches,
                exceptions,
                scope=effective_scope,
                as_of=effective_date,
            ),
            *self._low_confidence_findings(matches),
            *expired_signals,
            *expired_translation,
            *expired_required,
        ]
        findings = self._deduplicate_findings(findings)
        finding_counts = Counter(item.finding_code for item in findings)
        total_terms = len({term.id for term in terms if term.is_active})
        metrics = self.coverage.metrics(
            total_terms=total_terms,
            matches=matches,
            findings=findings,
        )
        return GlossaryValidationResult(
            matches=tuple(matches),
            findings=tuple(findings),
            total_terms=total_terms,
            matched_terms=len(
                {item.glossary_term_id for item in matches}
            ),
            preferred_term_matches=sum(
                item.is_preferred for item in matches
            ),
            forbidden_term_matches=sum(
                item.is_forbidden for item in matches
            ),
            missing_required_translations=finding_counts[
                "MISSING_GLOSSARY_TRANSLATION"
            ],
            inconsistent_terms=finding_counts[
                "INCONSISTENT_GLOSSARY_TRANSLATION"
            ],
            exception_applied_count=sum(
                item.exception_id is not None for item in matches
            )
            + len(translation_excepted)
            + len(required_term_excepted),
            metrics=metrics,
            warnings=tuple(warnings),
        )

    def _language_mismatch_findings(
        self,
        candidates: Sequence[GlossaryMatchCandidate],
        exceptions: Sequence[GlossaryException],
        *,
        scope: GlossaryValidationScope,
        as_of: date,
    ) -> list[GlossaryFindingSignal]:
        findings: list[GlossaryFindingSignal] = []
        for candidate in candidates:
            ignored, _ = self.exceptions.select_for_match(
                exceptions,
                candidate=candidate,
                exception_type=GlossaryExceptionType.IGNORE_TERM.value,
                scope=scope,
                as_of=as_of,
            )
            if ignored is not None:
                continue
            configured_language = str(
                candidate.metadata["configuredLanguage"]
            )
            findings.append(
                GlossaryFindingSignal(
                    finding_code="GLOSSARY_TERM_LANGUAGE_MISMATCH",
                    severity=candidate.severity,
                    title="Glossary term language mismatch detected",
                    description=(
                        f"'{candidate.matched_text}' is configured as a "
                        f"'{configured_language}' term but appears in a "
                        f"block detected as '{candidate.language_code}'."
                    ),
                    recommendation=(
                        "Review the detected block language and use the "
                        "approved translation for that language when "
                        "appropriate."
                    ),
                    glossary_term_id=candidate.glossary_term_id,
                    language_code=candidate.language_code,
                    source_reference=candidate.source_reference,
                    extracted_block_id=candidate.extracted_block_id,
                    ocr_block_id=candidate.ocr_block_id,
                    container_id=candidate.container_id,
                    detected_section_id=candidate.detected_section_id,
                    translation_group_id=candidate.translation_group_id,
                    metrics={
                        "termCode": candidate.term_code,
                        "matchedText": candidate.matched_text,
                        "configuredLanguage": configured_language,
                        "detectedLanguage": candidate.language_code,
                        "confidence": candidate.confidence,
                    },
                )
            )
        return findings

    def _apply_match_exceptions(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        exceptions: Sequence[GlossaryException],
        *,
        scope: GlossaryValidationScope,
        as_of: date,
    ) -> tuple[list[GlossaryMatchCandidate], list[GlossaryFindingSignal]]:
        resolved: list[GlossaryMatchCandidate] = []
        expired_signals: list[GlossaryFindingSignal] = []
        seen_expired: set[object] = set()
        for candidate in matches:
            exception_types = [GlossaryExceptionType.IGNORE_TERM]
            if candidate.is_forbidden:
                exception_types.append(
                    GlossaryExceptionType.ALLOW_FORBIDDEN_TERM
                )
            elif (
                not candidate.is_preferred
                and not candidate.is_allowed_variant
            ):
                exception_types.append(
                    GlossaryExceptionType.ALLOW_VARIANT
                )
            selected = None
            selected_type = None
            for exception_type in exception_types:
                active, expired = self.exceptions.select_for_match(
                    exceptions,
                    candidate=candidate,
                    exception_type=exception_type.value,
                    scope=scope,
                    as_of=as_of,
                )
                for item in expired:
                    if item.id not in seen_expired:
                        expired_signals.append(
                            self._expired_exception_signal(
                                item,
                                candidate,
                            )
                        )
                        seen_expired.add(item.id)
                if active is not None:
                    selected = active
                    selected_type = exception_type.value
                    break
            if selected is None:
                resolved.append(candidate)
            else:
                resolved.append(
                    replace(
                        candidate,
                        exception_id=selected.id,
                        metadata={
                            **candidate.metadata,
                            "exceptionType": selected_type,
                            "exceptionScope": selected.scope_type.value,
                        },
                    )
                )
        return resolved, expired_signals

    def _required_translation_exceptions(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        terms: Sequence[GlossaryTerm],
        exceptions: Sequence[GlossaryException],
        *,
        scope: GlossaryValidationScope,
        as_of: date,
    ) -> tuple[
        set[tuple[object, str, str]],
        list[GlossaryFindingSignal],
    ]:
        terms_by_id = {term.id: term for term in terms}
        grouped: dict[
            tuple[object, str],
            list[GlossaryMatchCandidate],
        ] = defaultdict(list)
        for item in matches:
            grouped[(item.glossary_term_id, item.context_key)].append(item)
        excepted: set[tuple[object, str, str]] = set()
        expired_findings: list[GlossaryFindingSignal] = []
        seen_expired: set[object] = set()
        for (term_id, context_key), context_matches in grouped.items():
            term = terms_by_id.get(term_id)
            if term is None:
                continue
            required = {
                translation.language_code.value
                for translation in term.translations
                if translation.is_active and translation.is_required
            }
            present = {item.language_code for item in context_matches}
            anchor = context_matches[0]
            for language in required - present:
                active, expired = self.exceptions.select(
                    exceptions,
                    term_id=term_id,
                    exception_type=(
                        GlossaryExceptionType.ALLOW_MISSING_TRANSLATION.value
                    ),
                    scope=scope,
                    language_code=language,
                    section_definition_id=anchor.section_definition_id,
                    as_of=as_of,
                )
                if active is not None:
                    excepted.add((term_id, context_key, language))
                for item in expired:
                    if item.id not in seen_expired:
                        expired_findings.append(
                            self._expired_exception_signal(item, anchor)
                        )
                        seen_expired.add(item.id)
        return excepted, expired_findings

    def _required_term_exceptions(
        self,
        matches: Sequence[GlossaryMatchCandidate],
        terms: Sequence[GlossaryTerm],
        exceptions: Sequence[GlossaryException],
        *,
        scope: GlossaryValidationScope,
        as_of: date,
    ) -> tuple[set[object], list[GlossaryFindingSignal]]:
        present = {item.glossary_term_id for item in matches}
        excepted: set[object] = set()
        expired_findings: list[GlossaryFindingSignal] = []
        for term in terms:
            if term.id in present:
                continue
            active, expired = self.exceptions.select(
                exceptions,
                term_id=term.id,
                exception_type=GlossaryExceptionType.IGNORE_TERM.value,
                scope=scope,
                as_of=as_of,
            )
            if active is not None:
                excepted.add(term.id)
            expired_findings.extend(
                self._expired_exception_signal(item, None)
                for item in expired
            )
        return excepted, expired_findings

    @staticmethod
    def _low_confidence_findings(
        matches: Sequence[GlossaryMatchCandidate],
    ) -> list[GlossaryFindingSignal]:
        return [
            GlossaryFindingSignal(
                finding_code="GLOSSARY_MATCH_LOW_CONFIDENCE",
                severity="INFORMATION",
                title="Glossary match has low source confidence",
                description=(
                    f"Term '{item.matched_text}' was matched in source "
                    "content with low extraction or OCR confidence."
                ),
                recommendation=(
                    "Review the extracted or OCR content before relying on "
                    "this glossary signal."
                ),
                glossary_term_id=item.glossary_term_id,
                language_code=item.language_code,
                source_reference=item.source_reference,
                extracted_block_id=item.extracted_block_id,
                ocr_block_id=item.ocr_block_id,
                container_id=item.container_id,
                detected_section_id=item.detected_section_id,
                translation_group_id=item.translation_group_id,
                exception_id=item.exception_id,
                metrics={
                    "termCode": item.term_code,
                    "confidence": item.confidence,
                },
            )
            for item in matches
            if item.confidence < 0.65
            and item.metadata.get("exceptionType") != "IGNORE_TERM"
        ]

    @staticmethod
    def _expired_exception_signal(
        item: GlossaryException,
        candidate: GlossaryMatchCandidate | None,
    ) -> GlossaryFindingSignal:
        return GlossaryFindingSignal(
            finding_code="GLOSSARY_EXCEPTION_EXPIRED",
            severity="INFORMATION",
            title="Glossary exception has expired",
            description=(
                "A glossary exception relevant to this validation is past "
                "its effective end date."
            ),
            recommendation=(
                "Review the exception and create a newly approved exception "
                "only when still justified."
            ),
            glossary_term_id=item.glossary_term_id,
            language_code=(
                candidate.language_code
                if candidate is not None
                else (
                    item.language_code.value
                    if item.language_code is not None
                    else None
                )
            ),
            source_reference=(
                candidate.source_reference
                if candidate is not None
                else None
            ),
            extracted_block_id=(
                candidate.extracted_block_id
                if candidate is not None
                else None
            ),
            ocr_block_id=(
                candidate.ocr_block_id
                if candidate is not None
                else None
            ),
            container_id=(
                candidate.container_id
                if candidate is not None
                else None
            ),
            detected_section_id=(
                candidate.detected_section_id
                if candidate is not None
                else None
            ),
            translation_group_id=(
                candidate.translation_group_id
                if candidate is not None
                else None
            ),
            exception_id=item.id,
            metrics={
                "exceptionType": item.exception_type.value,
                "exceptionScope": item.scope_type.value,
                "effectiveTo": (
                    item.effective_to.isoformat()
                    if item.effective_to is not None
                    else None
                ),
            },
        )

    @staticmethod
    def _deduplicate_findings(
        findings: Sequence[GlossaryFindingSignal],
    ) -> list[GlossaryFindingSignal]:
        retained: dict[tuple[object, ...], GlossaryFindingSignal] = {}
        for item in findings:
            key = (
                item.finding_code,
                item.glossary_term_id,
                item.language_code,
                item.source_reference,
                item.translation_group_id,
                item.exception_id,
            )
            retained.setdefault(key, item)
        return list(retained.values())
