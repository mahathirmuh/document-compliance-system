"""Hybrid Unicode, fastText, lexical-signal, and mixed-language detector."""

from __future__ import annotations

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
)
from app.schemas.language_internal import (
    LanguageDetectionData,
    LanguageScoreData,
)
from app.services.language.base_language_detector import BaseLanguageDetector
from app.services.language.fasttext_language_detector import (
    FastTextLanguageDetector,
)
from app.services.language.language_normalizer import (
    LanguageEligibilityEvaluator,
    normalize_language_text,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.services.language.mixed_language_detector import (
    MixedLanguageDetector,
)
from app.services.language.short_text_language_detector import (
    ShortTextLanguageDetector,
)
from app.services.language.unicode_script_detector import (
    UnicodeScriptDetector,
)


class HybridLanguageDetector(BaseLanguageDetector):
    """Apply deterministic guardrails around the local statistical model."""

    detector_name = "hybrid-unicode-fasttext"
    detector_version = "1.0"

    def __init__(
        self,
        fasttext_detector: FastTextLanguageDetector,
        config: LanguageRuntimeConfig,
    ) -> None:
        self.fasttext_detector = fasttext_detector
        self.config = config
        self.scripts = UnicodeScriptDetector()
        self.eligibility = LanguageEligibilityEvaluator(config)
        self.short_text = ShortTextLanguageDetector()
        self.mixed = MixedLanguageDetector(config)

    def detect(self, text: str) -> LanguageDetectionData:
        normalized = normalize_language_text(text)
        scripts = self.scripts.analyse(normalized)
        eligibility = self.eligibility.evaluate(normalized)
        word_count = self.short_text.word_count(normalized)
        if eligibility.status is LanguageEligibilityStatus.INELIGIBLE:
            return LanguageDetectionData(
                language_code=LanguageCode.UNKNOWN,
                primary_language_code=LanguageCode.UNKNOWN,
                confidence=0.0,
                is_mixed=False,
                detected_languages=[],
                script_statistics=scripts,
                eligibility=eligibility,
                character_count=len(normalized),
                latin_character_count=scripts.latin_character_count,
                han_character_count=scripts.han_character_count,
                word_count=word_count,
                metadata={"decision": "ineligible"},
            )

        raw_scores = self.fasttext_detector.predict_scores(normalized)
        scores = {
            item.language_code: item.score for item in raw_scores
        }
        lexical = self.short_text.signal_scores(normalized)
        signal_weight = (
            0.28
            if len(normalized) <= self.config.short_text_threshold
            else 0.14
        )
        for code, signal in lexical.items():
            scores[code] = min(
                1.0,
                scores.get(code, 0.0) + signal_weight * signal,
            )

        if scripts.han_ratio >= self.config.han_character_ratio_threshold:
            han_evidence = 0.55 + 0.45 * scripts.han_ratio
            scores[LanguageCode.CHINESE] = max(
                scores.get(LanguageCode.CHINESE, 0.0),
                min(0.99, han_evidence),
            )

        adjusted_scores = self._bounded_scores(scores)
        composition = self._normalized_scores(adjusted_scores)
        is_mixed = self.mixed.is_mixed(scripts, lexical)
        ranked = sorted(
            composition.items(),
            key=lambda item: (-item[1], item[0].value),
        )
        primary_code = (
            ranked[0][0] if ranked else LanguageCode.UNKNOWN
        )
        primary_evidence = adjusted_scores.get(primary_code, 0.0)
        if is_mixed:
            language_code = LanguageCode.MIXED
        elif primary_evidence < self.config.confidence_minimum:
            language_code = LanguageCode.UNKNOWN
        else:
            language_code = primary_code
        confidence = (
            primary_evidence
            if language_code is not LanguageCode.UNKNOWN
            else min(primary_evidence, self.config.confidence_minimum)
        )
        detected_languages = [
            LanguageScoreData(language_code=code, score=score)
            for code, score in ranked
            if score > 0
        ]
        return LanguageDetectionData(
            language_code=language_code,
            primary_language_code=primary_code,
            confidence=confidence,
            is_mixed=is_mixed,
            detected_languages=detected_languages,
            script_statistics=scripts,
            eligibility=eligibility,
            character_count=len(normalized),
            latin_character_count=scripts.latin_character_count,
            han_character_count=scripts.han_character_count,
            word_count=word_count,
            metadata={
                "rawFastTextScores": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in raw_scores
                ],
                "lexicalSignals": {
                    code.value: round(score, 6)
                    for code, score in lexical.items()
                },
                "confidenceNeedsReview": (
                    language_code is not LanguageCode.UNKNOWN
                    and confidence
                    < self.config.confidence_review_threshold
                ),
            },
        )

    @staticmethod
    def _bounded_scores(
        scores: dict[LanguageCode, float],
    ) -> dict[LanguageCode, float]:
        return {
            code: max(0.0, min(1.0, score))
            for code, score in scores.items()
            if code not in {LanguageCode.UNKNOWN, LanguageCode.MIXED}
            and score > 0
        }

    @staticmethod
    def _normalized_scores(
        bounded_scores: dict[LanguageCode, float],
    ) -> dict[LanguageCode, float]:
        total = sum(bounded_scores.values())
        if total <= 0:
            return {}
        return {
            code: score / total for code, score in bounded_scores.items()
        }

    def get_detector_info(self) -> dict[str, object]:
        return {
            "name": self.detector_name,
            "version": self.detector_version,
            "localOnly": True,
            "fastText": self.fasttext_detector.get_detector_info(),
            "confidenceMinimum": self.config.confidence_minimum,
            "hanRatioThreshold": (
                self.config.han_character_ratio_threshold
            ),
        }
