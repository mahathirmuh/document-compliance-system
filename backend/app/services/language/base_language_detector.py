"""Detector abstraction and stable failure types."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.language_internal import LanguageDetectionData


class LanguageDetectorError(RuntimeError):
    """A client-safe stable detector failure category."""

    error_code = "LANGUAGE_DETECTION_FAILED"


class LanguageModelNotAvailableError(LanguageDetectorError):
    """The configured local model cannot be used."""

    error_code = "LANGUAGE_MODEL_NOT_AVAILABLE"


class LanguageModelLoadError(LanguageDetectorError):
    """The local model exists but could not be loaded."""

    error_code = "LANGUAGE_MODEL_LOAD_FAILED"


class BaseLanguageDetector(ABC):
    """No database, network, file mutation, or audit side effects."""

    @abstractmethod
    def detect(self, text: str) -> LanguageDetectionData:
        """Detect one text block."""

    @abstractmethod
    def get_detector_info(self) -> dict[str, object]:
        """Return lightweight provenance/readiness details."""
