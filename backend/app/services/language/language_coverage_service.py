"""Preliminary block/character coverage and conservative presence rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
)
from app.schemas.language_internal import (
    CoverageBreakdownData,
    DetectedLanguageBlockData,
    LanguageDetectionData,
    LanguagePresenceData,
    LanguagePresenceState,
    PreliminaryCoverageData,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)

_COVERAGE_CODES = (
    LanguageCode.INDONESIAN,
    LanguageCode.ENGLISH,
    LanguageCode.CHINESE,
    LanguageCode.MIXED,
    LanguageCode.UNKNOWN,
    LanguageCode.OTHER,
)
_TARGET_CODES = (
    LanguageCode.INDONESIAN,
    LanguageCode.ENGLISH,
    LanguageCode.CHINESE,
)


class LanguageCoverageService:
    """Calculate coverage only; it never declares final compliance."""

    def __init__(self, config: LanguageRuntimeConfig) -> None:
        self.config = config

    def calculate(
        self,
        blocks: Sequence[DetectedLanguageBlockData],
    ) -> PreliminaryCoverageData:
        eligible = [
            block
            for block in blocks
            if block.detection.eligibility.status
            is LanguageEligibilityStatus.ELIGIBLE
        ]
        block_weights: dict[LanguageCode, float] = defaultdict(float)
        character_weights: dict[LanguageCode, float] = defaultdict(float)
        target_blocks: dict[LanguageCode, float] = defaultdict(float)
        target_characters: dict[LanguageCode, float] = defaultdict(float)
        for block in eligible:
            detection = block.detection
            composition = self._composition(detection)
            if composition is None:
                block_weights[detection.language_code] += 1.0
                character_weights[detection.language_code] += (
                    detection.character_count
                )
                if detection.language_code in _TARGET_CODES:
                    target_blocks[detection.language_code] += 1.0
                    target_characters[detection.language_code] += (
                        detection.character_count
                    )
                continue
            for code, weight in composition.items():
                block_weights[code] += weight
                character_weights[code] += (
                    detection.character_count * weight
                )
                if code in _TARGET_CODES:
                    target_blocks[code] += weight
                    target_characters[code] += (
                        detection.character_count * weight
                    )

        total_blocks = float(len(eligible))
        total_characters = float(
            sum(block.detection.character_count for block in eligible)
        )
        presence = LanguagePresenceData(
            id=self._presence(
                LanguageCode.INDONESIAN,
                eligible_blocks=len(eligible),
                eligible_characters=int(total_characters),
                blocks=target_blocks,
                characters=target_characters,
            ),
            en=self._presence(
                LanguageCode.ENGLISH,
                eligible_blocks=len(eligible),
                eligible_characters=int(total_characters),
                blocks=target_blocks,
                characters=target_characters,
            ),
            zh=self._presence(
                LanguageCode.CHINESE,
                eligible_blocks=len(eligible),
                eligible_characters=int(total_characters),
                blocks=target_blocks,
                characters=target_characters,
            ),
        )
        return PreliminaryCoverageData(
            block_coverage=self._breakdown(block_weights, total_blocks),
            character_coverage=self._breakdown(
                character_weights,
                total_characters,
            ),
            language_presence=presence,
            preliminary=True,
        )

    @staticmethod
    def _composition(
        detection: LanguageDetectionData,
    ) -> dict[LanguageCode, float] | None:
        if detection.language_code is not LanguageCode.MIXED:
            return None
        raw_scores = {
            item.language_code: item.score
            for item in detection.detected_languages
            if item.language_code in _TARGET_CODES and item.score > 0
        }
        total = sum(raw_scores.values())
        if total <= 0:
            return None
        return {code: score / total for code, score in raw_scores.items()}

    def _presence(
        self,
        code: LanguageCode,
        *,
        eligible_blocks: int,
        eligible_characters: int,
        blocks: dict[LanguageCode, float],
        characters: dict[LanguageCode, float],
    ) -> LanguagePresenceState:
        if (
            blocks.get(code, 0.0) >= self.config.presence_minimum_blocks
            and characters.get(code, 0.0)
            >= self.config.presence_minimum_characters
        ):
            return LanguagePresenceState.PRESENT
        if (
            eligible_blocks < self.config.presence_minimum_blocks
            or eligible_characters
            < self.config.presence_minimum_characters
        ):
            return LanguagePresenceState.INSUFFICIENT_EVIDENCE
        return LanguagePresenceState.NOT_PRESENT

    @staticmethod
    def _breakdown(
        weights: dict[LanguageCode, float],
        denominator: float,
    ) -> CoverageBreakdownData:
        values = {
            code.value: (
                round(weights.get(code, 0.0) * 100.0 / denominator, 2)
                if denominator
                else 0.0
            )
            for code in _COVERAGE_CODES
        }
        return CoverageBreakdownData(**values)
