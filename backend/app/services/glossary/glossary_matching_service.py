"""Local ID/EN/ZH glossary matching orchestration."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossaryTermType,
    GlossaryVariantType,
)
from app.services.glossary.contracts import (
    GlossaryMatchCandidate,
    GlossaryTextBlock,
)
from app.services.glossary.matching.chinese_term_matcher import (
    ChineseTermMatcher,
)
from app.services.glossary.matching.exact_term_matcher import (
    ExactTermMatcher,
    MatchSpan,
)
from app.services.glossary.matching.inflection_matcher import (
    InflectionMatcher,
)
from app.services.glossary.matching.regex_term_matcher import (
    GlossaryRegexTimeoutError,
    RegexTermMatcher,
    UnsafeGlossaryRegexError,
)
from app.services.glossary.matching.term_normalizer import normalize_term
from app.services.glossary.matching.whole_word_matcher import (
    WholeWordMatcher,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.glossary_term import GlossaryTerm
    from app.models.glossary_term_variant import GlossaryTermVariant
    from app.models.glossary_translation import GlossaryTranslation


class GlossaryMatchingService:
    """Match only already-extracted text; no binary or network access."""

    def __init__(
        self,
        *,
        term_max_length: int = 500,
        regex_max_length: int = 500,
        regex_timeout_ms: int = 100,
        maximum_blocks: int = 2_000_000,
    ) -> None:
        if term_max_length < 1 or maximum_blocks < 1:
            raise ValueError("Glossary matching limits must be positive.")
        self.term_max_length = term_max_length
        self.maximum_blocks = maximum_blocks
        self.exact = ExactTermMatcher()
        self.whole_word = WholeWordMatcher()
        self.inflection = InflectionMatcher()
        self.chinese = ChineseTermMatcher()
        self.regex = RegexTermMatcher(
            maximum_length=regex_max_length,
            timeout_ms=regex_timeout_ms,
        )

    def validate_regex_term(
        self,
        term: GlossaryTerm,
        text: str,
    ) -> None:
        """Compile one regex form during create/update."""

        if not term.is_regex:
            return
        self.regex.validate(
            text,
            case_sensitive=term.is_case_sensitive,
        )

    def match(
        self,
        blocks: Sequence[GlossaryTextBlock],
        terms: Sequence[GlossaryTerm],
    ) -> tuple[list[GlossaryMatchCandidate], list[str]]:
        if len(blocks) > self.maximum_blocks:
            raise ValueError(
                "Glossary validation exceeds the configured block limit."
            )
        selected_terms = self._overlay_terms(terms)
        matches: list[GlossaryMatchCandidate] = []
        warnings: list[str] = []
        for block in blocks:
            block_matches, block_warnings = self.match_block(
                block,
                selected_terms,
            )
            matches.extend(block_matches)
            warnings.extend(block_warnings)
        return self._deduplicate(matches), list(dict.fromkeys(warnings))

    def match_block(
        self,
        block: GlossaryTextBlock,
        terms: Sequence[GlossaryTerm],
    ) -> tuple[list[GlossaryMatchCandidate], list[str]]:
        if block.language_code not in {
            GlossaryLanguageCode.INDONESIAN.value,
            GlossaryLanguageCode.ENGLISH.value,
            GlossaryLanguageCode.CHINESE.value,
        }:
            return [], []
        if not block.text:
            return [], []
        candidates: list[GlossaryMatchCandidate] = []
        warnings: list[str] = []
        for term in terms:
            if not term.is_active:
                continue
            for translation in term.translations:
                if (
                    not translation.is_active
                    or translation.language_code.value
                    != block.language_code
                ):
                    continue
                try:
                    candidates.extend(
                        self._translation_matches(
                            block,
                            term,
                            translation,
                        )
                    )
                    for variant in translation.variants:
                        if variant.is_active:
                            candidates.extend(
                                self._variant_matches(
                                    block,
                                    term,
                                    translation,
                                    variant,
                                )
                            )
                except (
                    UnsafeGlossaryRegexError,
                    GlossaryRegexTimeoutError,
                ) as exc:
                    warnings.append(
                        f"{term.term_code}: {exc}"
                    )
        return self._deduplicate(candidates), warnings

    def detect_language_mismatches(
        self,
        blocks: Sequence[GlossaryTextBlock],
        terms: Sequence[GlossaryTerm],
    ) -> list[GlossaryMatchCandidate]:
        """Find configured foreign-language forms in a detected-language block.

        These candidates are review signals only and are deliberately kept
        out of the normal match set so they cannot satisfy required-language
        or preferred-term rules.
        """

        selected_terms = self._overlay_terms(terms)
        candidates: list[GlossaryMatchCandidate] = []
        for block in blocks:
            if block.language_code not in {
                GlossaryLanguageCode.INDONESIAN.value,
                GlossaryLanguageCode.ENGLISH.value,
                GlossaryLanguageCode.CHINESE.value,
            }:
                continue
            for term in selected_terms:
                if not term.is_active or term.is_regex:
                    continue
                configured_for_block = {
                    translation.normalised_term
                    for translation in term.translations
                    if translation.is_active
                    and translation.language_code.value
                    == block.language_code
                }
                for translation in term.translations:
                    if (
                        not translation.is_active
                        or translation.language_code.value
                        == block.language_code
                        or translation.normalised_term
                        in configured_for_block
                    ):
                        continue
                    for span in self._spans(
                        block,
                        term,
                        translation.term_text,
                        is_variant=False,
                    ):
                        candidates.append(
                            self._candidate(
                                block,
                                term,
                                translation,
                                None,
                                span,
                                is_preferred=translation.is_preferred,
                                is_forbidden=(
                                    term.term_type
                                    is GlossaryTermType.FORBIDDEN
                                    or translation.is_forbidden
                                ),
                                is_allowed_variant=False,
                            )
                        )
        return self._deduplicate(candidates)

    def _translation_matches(
        self,
        block: GlossaryTextBlock,
        term: GlossaryTerm,
        translation: GlossaryTranslation,
    ) -> list[GlossaryMatchCandidate]:
        spans = self._spans(
            block,
            term,
            translation.term_text,
            is_variant=False,
        )
        forbidden = (
            term.term_type is GlossaryTermType.FORBIDDEN
            or translation.is_forbidden
        )
        return [
            self._candidate(
                block,
                term,
                translation,
                None,
                span,
                is_preferred=translation.is_preferred,
                is_forbidden=forbidden,
                is_allowed_variant=False,
            )
            for span in spans
        ]

    def _variant_matches(
        self,
        block: GlossaryTextBlock,
        term: GlossaryTerm,
        translation: GlossaryTranslation,
        variant: GlossaryTermVariant,
    ) -> list[GlossaryMatchCandidate]:
        spans = self._spans(
            block,
            term,
            variant.variant_text,
            is_variant=True,
        )
        forbidden = (
            term.term_type is GlossaryTermType.FORBIDDEN
            or translation.is_forbidden
            or variant.variant_type is GlossaryVariantType.FORBIDDEN_VARIANT
        )
        return [
            self._candidate(
                block,
                term,
                translation,
                variant,
                replace(span, match_type=GlossaryMatchType.VARIANT),
                is_preferred=False,
                is_forbidden=forbidden,
                is_allowed_variant=variant.is_allowed and not forbidden,
            )
            for span in spans
        ]

    def _spans(
        self,
        block: GlossaryTextBlock,
        term: GlossaryTerm,
        term_text: str,
        *,
        is_variant: bool,
    ) -> list[MatchSpan]:
        if len(term_text) > self.term_max_length:
            return []
        if term.is_regex and not is_variant:
            return self.regex.find(
                block.text,
                term_text,
                case_sensitive=term.is_case_sensitive,
            )
        if block.language_code == GlossaryLanguageCode.CHINESE.value:
            return self.chinese.find(
                block.text,
                term_text,
                case_sensitive=term.is_case_sensitive,
            )
        if term.allow_inflection:
            return self.inflection.find(
                block.text,
                term_text,
                case_sensitive=term.is_case_sensitive,
            )
        if term.match_whole_word:
            return self.whole_word.find(
                block.text,
                term_text,
                case_sensitive=term.is_case_sensitive,
            )
        return self.exact.find(
            block.text,
            term_text,
            case_sensitive=term.is_case_sensitive,
        )

    @staticmethod
    def _candidate(
        block: GlossaryTextBlock,
        term: GlossaryTerm,
        translation: GlossaryTranslation,
        variant: GlossaryTermVariant | None,
        span: MatchSpan,
        *,
        is_preferred: bool,
        is_forbidden: bool,
        is_allowed_variant: bool,
    ) -> GlossaryMatchCandidate:
        matched = block.text[span.start : span.end]
        return GlossaryMatchCandidate(
            glossary_term_id=term.id,
            glossary_translation_id=translation.id,
            glossary_variant_id=variant.id if variant is not None else None,
            term_code=term.term_code,
            concept_name=term.concept_name,
            term_type=term.term_type.value,
            severity=term.severity.value,
            language_code=block.language_code,
            source_type=block.source_type,
            source_reference=block.source_reference,
            matched_text=matched[:500],
            normalised_matched_text=normalize_term(
                matched,
                case_sensitive=term.is_case_sensitive,
            )[:500],
            start_offset=span.start,
            end_offset=span.end,
            match_type=span.match_type.value,
            is_preferred=is_preferred,
            is_forbidden=is_forbidden,
            is_allowed_variant=is_allowed_variant,
            extracted_block_id=block.extracted_block_id,
            ocr_block_id=block.ocr_block_id,
            container_id=block.container_id,
            detected_section_id=block.detected_section_id,
            section_definition_id=block.section_definition_id,
            translation_group_id=block.translation_group_id,
            confidence=max(0.0, min(1.0, block.confidence)),
            metadata={
                "configuredLanguage": translation.language_code.value,
                "variantType": (
                    variant.variant_type.value
                    if variant is not None
                    else None
                ),
            },
        )

    @staticmethod
    def _overlay_terms(
        terms: Sequence[GlossaryTerm],
    ) -> list[GlossaryTerm]:
        """First profile wins for duplicate term codes."""

        selected: dict[str, GlossaryTerm] = {}
        for term in terms:
            selected.setdefault(term.term_code, term)
        return list(selected.values())

    @staticmethod
    def _deduplicate(
        matches: Sequence[GlossaryMatchCandidate],
    ) -> list[GlossaryMatchCandidate]:
        retained: dict[
            tuple[object, ...],
            GlossaryMatchCandidate,
        ] = {}
        for candidate in matches:
            key = (
                candidate.glossary_term_id,
                candidate.source_type,
                candidate.extracted_block_id,
                candidate.ocr_block_id,
                candidate.source_reference,
                candidate.start_offset,
                candidate.end_offset,
            )
            previous = retained.get(key)
            if previous is None:
                retained[key] = candidate
                continue
            if (
                previous.glossary_variant_id is not None
                and candidate.glossary_variant_id is None
            ):
                retained[key] = candidate
        return sorted(
            retained.values(),
            key=lambda item: (
                item.source_reference,
                item.start_offset,
                item.end_offset,
                item.term_code,
            ),
        )
