"""Document and container aggregation for hybrid block decisions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
)
from app.schemas.language_internal import (
    AggregatedLanguageData,
    DetectedLanguageBlockData,
    LanguageContainerAggregateData,
)
from app.services.language.language_coverage_service import (
    LanguageCoverageService,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)


class LanguageAggregationService:
    """Aggregate retained detector results without making compliance claims."""

    def __init__(self, config: LanguageRuntimeConfig) -> None:
        self.coverage = LanguageCoverageService(config)

    def aggregate(
        self,
        blocks: Sequence[DetectedLanguageBlockData],
    ) -> AggregatedLanguageData:
        counts: dict[LanguageCode, int] = defaultdict(int)
        characters: dict[LanguageCode, int] = defaultdict(int)
        eligible = 0
        detected = 0
        confidences: list[float] = []
        for block in blocks:
            result = block.detection
            counts[result.language_code] += 1
            characters[result.language_code] += result.character_count
            if (
                result.eligibility.status
                is LanguageEligibilityStatus.ELIGIBLE
            ):
                eligible += 1
                if result.language_code is not LanguageCode.UNKNOWN:
                    detected += 1
                    confidences.append(result.confidence)

        dominant_candidates = {
            code: characters.get(code, 0)
            for code in (
                LanguageCode.INDONESIAN,
                LanguageCode.ENGLISH,
                LanguageCode.CHINESE,
                LanguageCode.MIXED,
                LanguageCode.OTHER,
            )
        }
        dominant = max(
            dominant_candidates,
            key=lambda code: (
                dominant_candidates[code],
                -list(dominant_candidates).index(code),
            ),
        )
        if dominant_candidates[dominant] == 0:
            dominant = LanguageCode.UNKNOWN
        return AggregatedLanguageData(
            total_blocks=len(blocks),
            eligible_blocks=eligible,
            detected_blocks=detected,
            unknown_blocks=counts[LanguageCode.UNKNOWN],
            mixed_blocks=counts[LanguageCode.MIXED],
            indonesian_blocks=counts[LanguageCode.INDONESIAN],
            english_blocks=counts[LanguageCode.ENGLISH],
            chinese_blocks=counts[LanguageCode.CHINESE],
            other_blocks=counts[LanguageCode.OTHER],
            total_characters=sum(
                block.detection.character_count for block in blocks
            ),
            indonesian_characters=characters[LanguageCode.INDONESIAN],
            english_characters=characters[LanguageCode.ENGLISH],
            chinese_characters=characters[LanguageCode.CHINESE],
            mixed_characters=characters[LanguageCode.MIXED],
            unknown_characters=characters[LanguageCode.UNKNOWN],
            other_characters=characters[LanguageCode.OTHER],
            average_confidence=(
                sum(confidences) / len(confidences)
                if confidences
                else None
            ),
            dominant_language=dominant,
            coverage=self.coverage.calculate(blocks),
        )

    def aggregate_containers(
        self,
        blocks: Sequence[DetectedLanguageBlockData],
    ) -> list[LanguageContainerAggregateData]:
        grouped: dict[
            tuple[UUID | None, str, str | None, int],
            list[DetectedLanguageBlockData],
        ] = defaultdict(list)
        for block in blocks:
            source = block.source
            grouped[
                (
                    source.container_id,
                    source.container_type,
                    source.container_name,
                    source.container_index,
                )
            ].append(block)
        return [
            LanguageContainerAggregateData(
                container_id=container_id,
                container_type=container_type,
                container_name=container_name,
                container_index=container_index,
                aggregate=self.aggregate(container_blocks),
            )
            for (
                container_id,
                container_type,
                container_name,
                container_index,
            ), container_blocks in sorted(
                grouped.items(),
                key=lambda item: (
                    item[0][3],
                    item[0][1],
                    str(item[0][0] or ""),
                ),
            )
        ]
