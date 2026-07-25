"""Construct local OCR providers with test-safe dependency injection."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.services.ocr.base_ocr_provider import (
    BaseOCRProvider,
    OCRProviderUnavailableError,
)
from app.services.ocr.paddle_ocr_provider import PaddleOCRProvider

if TYPE_CHECKING:
    from app.core.config import Settings


class OCRProviderFactory:
    """Resolve configured local providers without importing heavy models."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        injected_provider: BaseOCRProvider | None = None,
    ) -> None:
        self.settings = settings
        self.injected_provider = injected_provider

    def create(self, provider_name: str | None = None) -> BaseOCRProvider:
        if self.injected_provider is not None:
            return self.injected_provider
        configured = provider_name or getattr(
            self.settings,
            "ocr_provider",
            "paddleocr",
        )
        normalized = str(configured).strip().lower()
        if normalized == "paddleocr":
            return PaddleOCRProvider(
                model_root=Path(
                    getattr(
                        self.settings,
                        "ocr_model_root",
                        "models/ocr",
                    )
                ),
                latin_recognition_model_name=str(
                    getattr(
                        self.settings,
                        "ocr_latin_model_name",
                        "latin_PP-OCRv5_mobile_rec",
                    )
                ),
                chinese_recognition_model_name=str(
                    getattr(
                        self.settings,
                        "ocr_chinese_model_name",
                        "PP-OCRv5_mobile_rec",
                    )
                ),
            )
        raise OCRProviderUnavailableError(
            "OCR_PROVIDER_UNAVAILABLE",
            "The configured local OCR provider is not available.",
            details={"provider": normalized},
        )


def get_ocr_provider(
    settings: Settings | None = None,
    *,
    injected_provider: BaseOCRProvider | None = None,
) -> BaseOCRProvider:
    """Return one provider facade; model objects remain process-cached."""
    return OCRProviderFactory(
        settings,
        injected_provider=injected_provider,
    ).create()
