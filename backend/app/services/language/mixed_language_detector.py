"""Mixed-target-language decision rules."""

from __future__ import annotations

from app.models.language_block_result import LanguageCode
from app.schemas.language_internal import ScriptStatisticsData
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)


class MixedLanguageDetector:
    """Recognise mixed target-language evidence independent of model rank."""

    def __init__(self, config: LanguageRuntimeConfig) -> None:
        self.config = config

    def is_mixed(
        self,
        scripts: ScriptStatisticsData,
        lexical_signals: dict[LanguageCode, float],
    ) -> bool:
        dual_lexical_evidence = (
            lexical_signals.get(LanguageCode.INDONESIAN, 0.0)
            >= self.config.mixed_secondary_score_threshold
            and lexical_signals.get(LanguageCode.ENGLISH, 0.0)
            >= self.config.mixed_secondary_score_threshold
        )
        dual_script_evidence = (
            scripts.han_ratio
            >= self.config.mixed_min_character_ratio
            and scripts.latin_ratio
            >= self.config.mixed_min_character_ratio
        )
        return dual_lexical_evidence or dual_script_evidence
