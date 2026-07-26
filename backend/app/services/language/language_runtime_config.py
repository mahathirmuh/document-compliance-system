"""One validated view over Phase 7 language-related application settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LanguageRuntimeConfig:
    """Runtime limits kept out of detector and aggregation algorithms."""

    model_path: Path = Path("/app/models/language/lid.176.bin")
    minimum_characters: int = 4
    minimum_alpha_characters: int = 3
    short_text_threshold: int = 20
    confidence_minimum: float = 0.55
    confidence_review_threshold: float = 0.75
    han_character_ratio_threshold: float = 0.20
    mixed_secondary_score_threshold: float = 0.25
    mixed_min_character_ratio: float = 0.15
    presence_minimum_blocks: int = 2
    presence_minimum_characters: int = 20
    database_batch_size: int = 1000
    maximum_blocks: int = 2_000_000
    export_maximum_blocks: int = 2_000_000
    native_page_minimum_characters: int = 50
    maximum_retries: int = 2

    @classmethod
    def from_settings(cls, settings: Any) -> LanguageRuntimeConfig:
        """Read shared Settings fields without coupling pure tests to it."""
        defaults = cls()
        return cls(
            model_path=Path(
                getattr(
                    settings,
                    "language_model_path",
                    defaults.model_path,
                )
            ),
            minimum_characters=int(
                getattr(
                    settings,
                    "language_min_characters",
                    defaults.minimum_characters,
                )
            ),
            minimum_alpha_characters=int(
                getattr(
                    settings,
                    "language_min_alpha_characters",
                    defaults.minimum_alpha_characters,
                )
            ),
            short_text_threshold=int(
                getattr(
                    settings,
                    "language_short_text_threshold",
                    defaults.short_text_threshold,
                )
            ),
            confidence_minimum=float(
                getattr(
                    settings,
                    "language_confidence_minimum",
                    defaults.confidence_minimum,
                )
            ),
            confidence_review_threshold=float(
                getattr(
                    settings,
                    "language_confidence_review_threshold",
                    defaults.confidence_review_threshold,
                )
            ),
            han_character_ratio_threshold=float(
                getattr(
                    settings,
                    "language_han_character_ratio_threshold",
                    defaults.han_character_ratio_threshold,
                )
            ),
            mixed_secondary_score_threshold=float(
                getattr(
                    settings,
                    "language_mixed_secondary_score_threshold",
                    defaults.mixed_secondary_score_threshold,
                )
            ),
            mixed_min_character_ratio=float(
                getattr(
                    settings,
                    "language_mixed_min_character_ratio",
                    defaults.mixed_min_character_ratio,
                )
            ),
            presence_minimum_blocks=int(
                getattr(
                    settings,
                    "language_presence_min_blocks",
                    defaults.presence_minimum_blocks,
                )
            ),
            presence_minimum_characters=int(
                getattr(
                    settings,
                    "language_presence_min_characters",
                    defaults.presence_minimum_characters,
                )
            ),
            database_batch_size=int(
                getattr(
                    settings,
                    "language_detection_db_batch_size",
                    defaults.database_batch_size,
                )
            ),
            maximum_blocks=int(
                getattr(
                    settings,
                    "language_detection_max_blocks",
                    defaults.maximum_blocks,
                )
            ),
            export_maximum_blocks=int(
                getattr(
                    settings,
                    "language_export_max_blocks",
                    defaults.export_maximum_blocks,
                )
            ),
            native_page_minimum_characters=int(
                getattr(
                    settings,
                    "ocr_selectable_text_min_characters",
                    defaults.native_page_minimum_characters,
                )
            ),
            maximum_retries=int(
                getattr(
                    settings,
                    "language_max_retries",
                    defaults.maximum_retries,
                )
            ),
        )

    def __post_init__(self) -> None:
        positive_fields = {
            "minimum_characters": self.minimum_characters,
            "minimum_alpha_characters": self.minimum_alpha_characters,
            "short_text_threshold": self.short_text_threshold,
            "presence_minimum_blocks": self.presence_minimum_blocks,
            "presence_minimum_characters": self.presence_minimum_characters,
            "database_batch_size": self.database_batch_size,
            "maximum_blocks": self.maximum_blocks,
            "export_maximum_blocks": self.export_maximum_blocks,
            "native_page_minimum_characters": (
                self.native_page_minimum_characters
            ),
        }
        for name, value in positive_fields.items():
            if value < 1:
                raise ValueError(f"{name} must be positive.")
        thresholds = {
            "confidence_minimum": self.confidence_minimum,
            "confidence_review_threshold": (
                self.confidence_review_threshold
            ),
            "han_character_ratio_threshold": (
                self.han_character_ratio_threshold
            ),
            "mixed_secondary_score_threshold": (
                self.mixed_secondary_score_threshold
            ),
            "mixed_min_character_ratio": self.mixed_min_character_ratio,
        }
        for threshold_name, threshold_value in thresholds.items():
            if not 0 <= threshold_value <= 1:
                raise ValueError(
                    f"{threshold_name} must be between zero and one."
                )
        if self.maximum_retries < 0:
            raise ValueError("maximum_retries must be nonnegative.")
