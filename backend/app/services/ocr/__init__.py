"""Local scanned-PDF OCR pipeline."""

from app.services.ocr.base_ocr_provider import BaseOCRProvider
from app.services.ocr.ocr_provider_factory import get_ocr_provider

__all__ = ["BaseOCRProvider", "get_ocr_provider"]
