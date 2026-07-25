"""Bounded, temporary PyMuPDF page rendering for OCR."""

from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

from app.schemas.ocr_internal import OCRRenderedPage
from app.services.ocr.base_ocr_provider import (
    OCRError,
    OCRResourceLimitError,
)


class OCRRenderService:
    """Render exactly one requested PDF page without altering the PDF."""

    def __init__(
        self,
        *,
        dpi: int = 300,
        image_format: str = "png",
        maximum_width: int = 6000,
        maximum_height: int = 6000,
    ) -> None:
        normalized_format = image_format.strip().lower()
        if normalized_format not in {"png"}:
            raise ValueError("OCR render format must be png.")
        if dpi < 72:
            raise ValueError("OCR render DPI must be at least 72.")
        self.dpi = dpi
        self.image_format = normalized_format
        self.maximum_width = maximum_width
        self.maximum_height = maximum_height

    async def render_page(
        self,
        pdf_path: Path,
        page_number: int,
        output_directory: Path,
    ) -> OCRRenderedPage:
        return await asyncio.to_thread(
            self._render_page_sync,
            pdf_path,
            page_number,
            output_directory,
        )

    def _render_page_sync(
        self,
        pdf_path: Path,
        page_number: int,
        output_directory: Path,
    ) -> OCRRenderedPage:
        if page_number < 1:
            raise OCRError(
                "OCR_RENDER_FAILED",
                "OCR page numbers must start at one.",
            )
        if not pdf_path.is_file():
            raise OCRError(
                "OCR_RENDER_FAILED",
                "The source PDF is not available for rendering.",
            )
        try:
            import pymupdf
        except (ImportError, OSError) as exc:
            raise OCRError(
                "OCR_RENDER_FAILED",
                "The local PDF rendering runtime is unavailable.",
            ) from exc

        document = None
        output_path: Path | None = None
        try:
            document = pymupdf.open(pdf_path)
            if document.needs_pass:
                raise OCRError(
                    "OCR_RENDER_FAILED",
                    "Password-protected PDFs cannot be rendered for OCR.",
                )
            if page_number > document.page_count:
                raise OCRError(
                    "OCR_RENDER_FAILED",
                    "The requested OCR page does not exist in this PDF.",
                )
            page = document.load_page(page_number - 1)
            scale = self.dpi / 72
            expected_width = max(1, round(float(page.rect.width) * scale))
            expected_height = max(1, round(float(page.rect.height) * scale))
            if (
                expected_width > self.maximum_width
                or expected_height > self.maximum_height
            ):
                raise OCRResourceLimitError(
                    "OCR_RENDER_FAILED",
                    "The rendered OCR page would exceed configured dimensions.",
                    details={
                        "pageNumber": page_number,
                        "width": expected_width,
                        "height": expected_height,
                        "maximumWidth": self.maximum_width,
                        "maximumHeight": self.maximum_height,
                    },
                )
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = output_directory / (
                f"page-{page_number}-{secrets.token_hex(8)}.{self.image_format}"
            )
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                alpha=False,
                colorspace=pymupdf.csRGB,
            )
            if pixmap.width > self.maximum_width or pixmap.height > self.maximum_height:
                raise OCRResourceLimitError(
                    "OCR_RENDER_FAILED",
                    "The rendered OCR page exceeded configured dimensions.",
                )
            pixmap.save(output_path)
            return OCRRenderedPage(
                page_number=page_number,
                image_path=output_path,
                width=pixmap.width,
                height=pixmap.height,
                dpi=self.dpi,
                source_rotation=int(page.rotation) % 360,
            )
        except (OCRError, OCRResourceLimitError):
            if output_path is not None:
                output_path.unlink(missing_ok=True)
            raise
        except (RuntimeError, ValueError, OSError) as exc:
            if output_path is not None:
                output_path.unlink(missing_ok=True)
            raise OCRError(
                "OCR_RENDER_FAILED",
                "The PDF page could not be rendered for OCR.",
                details={"pageNumber": page_number},
            ) from exc
        finally:
            if document is not None:
                document.close()

    @staticmethod
    async def remove_rendered_page(path: Path) -> None:
        await asyncio.to_thread(path.unlink, missing_ok=True)
