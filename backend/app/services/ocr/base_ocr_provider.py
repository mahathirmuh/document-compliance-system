"""Provider-neutral OCR contract and controlled pipeline errors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.schemas.ocr_internal import OCRPageResult


class OCRError(Exception):
    """Client-safe OCR failure with a stable error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.details = dict(details or {})


class OCRProviderUnavailableError(OCRError):
    """Provider/model dependency is missing or could not initialize."""


class OCRResourceLimitError(OCRError):
    """Input would exceed configured OCR resource boundaries."""


class OCRTransientError(OCRError):
    """Infrastructure failure that may safely be retried."""


class OCRCancelledError(OCRError):
    """Cancellation observed at a safe inter-page/pass checkpoint."""

    def __init__(self) -> None:
        super().__init__("OCR_CANCELLED", "OCR processing was cancelled.")


class BaseOCRProvider(ABC):
    """Pure recognition provider: no database, document, or audit writes."""

    @abstractmethod
    async def recognise_page(
        self,
        image_path: Path,
        language_profile: str,
        options: dict,
    ) -> OCRPageResult:
        """Recognise one private rendered page."""

    @abstractmethod
    def supports_language_profile(
        self,
        language_profile: str,
    ) -> bool:
        """Return whether a bounded profile is available."""

    @abstractmethod
    def get_provider_info(self) -> dict:
        """Return lightweight readiness metadata without loading models."""
