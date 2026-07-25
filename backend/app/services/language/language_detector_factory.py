"""Build production or explicitly injected hybrid detectors."""

from __future__ import annotations

from typing import Any

from app.services.language.fasttext_language_detector import (
    FastTextLanguageDetector,
    FastTextPredictor,
)
from app.services.language.hybrid_language_detector import (
    HybridLanguageDetector,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)

_worker_detector: HybridLanguageDetector | None = None


class LanguageDetectorFactory:
    """Model injection keeps tests independent from the large binary."""

    @staticmethod
    def create(
        settings: Any,
        *,
        predictor: FastTextPredictor | None = None,
    ) -> HybridLanguageDetector:
        config = LanguageRuntimeConfig.from_settings(settings)
        fasttext_detector = FastTextLanguageDetector(
            config.model_path,
            predictor=predictor,
        )
        return HybridLanguageDetector(fasttext_detector, config)


def get_worker_language_detector(settings: Any) -> HybridLanguageDetector:
    """Cache one lazily-loaded, read-only model per Celery child process."""
    global _worker_detector
    if _worker_detector is None:
        _worker_detector = LanguageDetectorFactory.create(settings)
    return _worker_detector
