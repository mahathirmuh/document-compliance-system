"""Lazy, local-only fastText lid.176 adapter with injectable test model."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Protocol, cast

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
)
from app.schemas.language_internal import (
    LanguageDetectionData,
    LanguageEligibilityData,
    LanguageScoreData,
)
from app.services.language.base_language_detector import (
    BaseLanguageDetector,
    LanguageModelLoadError,
    LanguageModelNotAvailableError,
)
from app.services.language.language_normalizer import normalize_language_text
from app.services.language.short_text_language_detector import (
    ShortTextLanguageDetector,
)
from app.services.language.unicode_script_detector import (
    UnicodeScriptDetector,
)


class FastTextPredictor(Protocol):
    def predict(
        self,
        text: str,
        *,
        k: int,
    ) -> tuple[Sequence[str], Sequence[float]]: ...


class FastTextNativeBinding(Protocol):
    def predict(
        self,
        text: str,
        k: int,
        threshold: float,
        on_unicode_error: str,
    ) -> Sequence[tuple[float, str]]: ...


class FastTextNativePredictor(FastTextPredictor, Protocol):
    f: FastTextNativeBinding


_TARGET_LABELS = {
    "id": LanguageCode.INDONESIAN,
    "en": LanguageCode.ENGLISH,
    "zh": LanguageCode.CHINESE,
    "zh-cn": LanguageCode.CHINESE,
}


class FastTextLanguageDetector(BaseLanguageDetector):
    """Load the configured binary once per worker process, on first use."""

    detector_name = "fastText lid.176"
    detector_version = "176"

    def __init__(
        self,
        model_path: Path,
        *,
        predictor: FastTextPredictor | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self._predictor = predictor
        self._injected = predictor is not None
        self._script_detector = UnicodeScriptDetector()

    @property
    def path_ready(self) -> bool:
        return self._injected or (
            self.model_path.is_file() and self.model_path.stat().st_size > 0
        )

    @property
    def runtime_ready(self) -> bool:
        return self._injected or find_spec("fasttext") is not None

    def ensure_loaded(self) -> FastTextPredictor:
        if self._predictor is not None:
            return self._predictor
        if not self.path_ready:
            raise LanguageModelNotAvailableError(
                "The local fastText language model is not available."
            )
        try:
            fasttext = importlib.import_module("fasttext")
            loader = fasttext.load_model
            model = loader(str(self.model_path))
        except ModuleNotFoundError as exc:
            raise LanguageModelNotAvailableError(
                "The local fastText runtime is not installed."
            ) from exc
        except Exception as exc:
            raise LanguageModelLoadError(
                "The local fastText language model could not be loaded."
            ) from exc
        self._predictor = cast(FastTextPredictor, model)
        return self._predictor

    def predict_scores(self, text: str, *, k: int = 5) -> list[LanguageScoreData]:
        predictor = self.ensure_loaded()
        normalized = normalize_language_text(text).replace("\n", " ")
        try:
            labels, probabilities = predictor.predict(normalized, k=k)
        except ValueError as exc:
            if "copy" not in str(exc).casefold():
                raise LanguageModelLoadError(
                    "The local fastText model could not produce a prediction."
                ) from exc
            try:
                native = cast(FastTextNativePredictor, predictor)
                predictions = native.f.predict(
                    f"{normalized}\n",
                    k,
                    0.0,
                    "strict",
                )
                probabilities = [
                    probability for probability, _ in predictions
                ]
                labels = [label for _, label in predictions]
            except Exception as native_exc:
                raise LanguageModelLoadError(
                    "The local fastText model could not produce a prediction."
                ) from native_exc
        except Exception as exc:
            raise LanguageModelLoadError(
                "The local fastText model could not produce a prediction."
            ) from exc
        merged: dict[LanguageCode, float] = {}
        for raw_label, probability in zip(
            labels,
            probabilities,
            strict=False,
        ):
            label = str(raw_label).removeprefix("__label__").casefold()
            language = _TARGET_LABELS.get(label, LanguageCode.OTHER)
            merged[language] = max(
                merged.get(language, 0.0),
                max(0.0, min(1.0, float(probability))),
            )
        return [
            LanguageScoreData(language_code=language, score=score)
            for language, score in sorted(
                merged.items(),
                key=lambda item: (-item[1], item[0].value),
            )
        ]

    def detect(self, text: str) -> LanguageDetectionData:
        normalized = normalize_language_text(text)
        scripts = self._script_detector.analyse(normalized)
        scores = self.predict_scores(normalized)
        primary = (
            scores[0]
            if scores
            else LanguageScoreData(
                language_code=LanguageCode.UNKNOWN,
                score=0.0,
            )
        )
        return LanguageDetectionData(
            language_code=primary.language_code,
            primary_language_code=primary.language_code,
            confidence=primary.score,
            is_mixed=False,
            detected_languages=scores,
            script_statistics=scripts,
            eligibility=LanguageEligibilityData(
                status=LanguageEligibilityStatus.ELIGIBLE,
                reason=None,
            ),
            character_count=len(normalized),
            latin_character_count=scripts.latin_character_count,
            han_character_count=scripts.han_character_count,
            word_count=ShortTextLanguageDetector.word_count(normalized),
            metadata={"rawFastTextScores": [score.model_dump() for score in scores]},
        )

    def get_detector_info(self) -> dict[str, object]:
        return {
            "name": self.detector_name,
            "version": self.detector_version,
            "modelPath": str(self.model_path),
            "modelPathReady": self.path_ready,
            "runtimeReady": self.runtime_ready,
            "ready": self.path_ready and self.runtime_ready,
            "modelLoaded": self._predictor is not None,
            "injectedPredictor": self._injected,
            "localOnly": True,
        }
