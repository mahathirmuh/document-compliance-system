"""Local Pillow/OpenCV preprocessing for rendered OCR pages."""

from __future__ import annotations

import asyncio
import secrets
from typing import Any

from app.models.ocr_job import OCRPreprocessingProfile
from app.schemas.ocr_internal import (
    OCRPreprocessedPage,
    OCRRenderedPage,
)
from app.services.ocr.base_ocr_provider import OCRError


class OCRPreprocessingService:
    """Apply bounded grayscale/contrast/deskew cleanup to a private image."""

    async def preprocess(
        self,
        rendered: OCRRenderedPage,
        profile: OCRPreprocessingProfile,
    ) -> OCRPreprocessedPage:
        if profile is OCRPreprocessingProfile.NONE:
            return OCRPreprocessedPage(
                page_number=rendered.page_number,
                image_path=rendered.image_path,
                width=rendered.width,
                height=rendered.height,
                rotation_applied=0,
                deskew_angle=None,
                metadata={"profile": profile.value, "copied": False},
            )
        return await asyncio.to_thread(
            self._preprocess_sync,
            rendered,
            profile,
        )

    def _preprocess_sync(
        self,
        rendered: OCRRenderedPage,
        profile: OCRPreprocessingProfile,
    ) -> OCRPreprocessedPage:
        output_path = rendered.image_path.with_name(
            f"{rendered.image_path.stem}-processed-{secrets.token_hex(6)}.png"
        )
        try:
            from PIL import Image, ImageEnhance, ImageFilter, ImageOps

            with Image.open(rendered.image_path) as source:
                image = ImageOps.grayscale(source)
                resized = False
                if min(image.size) < 1000:
                    scale = min(2.0, 1000 / max(1, min(image.size)))
                    image = image.resize(
                        (
                            max(1, round(image.width * scale)),
                            max(1, round(image.height * scale)),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                    resized = True
                image = ImageEnhance.Contrast(image).enhance(
                    1.25 if profile is OCRPreprocessingProfile.STANDARD else 1.55
                )
                if profile is OCRPreprocessingProfile.STANDARD:
                    image = image.filter(ImageFilter.MedianFilter(size=3))
                else:
                    image = image.filter(ImageFilter.MedianFilter(size=5))
                    image = image.filter(ImageFilter.SHARPEN)
                deskewed, deskew_angle, backend = self._deskew_and_threshold(
                    image,
                    aggressive=(profile is OCRPreprocessingProfile.AGGRESSIVE),
                )
                deskewed.save(output_path, format="PNG", optimize=True)
                width, height = deskewed.size
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            output_path.unlink(missing_ok=True)
            raise OCRError(
                "OCR_PREPROCESSING_FAILED",
                "The rendered page could not be preprocessed for OCR.",
                details={"profile": profile.value},
            ) from exc

        return OCRPreprocessedPage(
            page_number=rendered.page_number,
            image_path=output_path,
            width=width,
            height=height,
            rotation_applied=0,
            deskew_angle=deskew_angle,
            metadata={
                "profile": profile.value,
                "backend": backend,
                "grayscale": True,
                "contrastAdjusted": True,
                "denoised": True,
                "resized": resized,
                "thresholded": (profile is OCRPreprocessingProfile.AGGRESSIVE),
            },
        )

    @staticmethod
    def _deskew_and_threshold(
        image: Any,
        *,
        aggressive: bool,
    ) -> tuple[Any, float | None, str]:
        """Use OpenCV when available and preserve Pillow-only portability."""
        try:
            import cv2
            import numpy as np
            from PIL import Image
        except (ImportError, OSError):
            return image, None, "pillow"

        array = np.asarray(image)
        inverted = cv2.bitwise_not(array)
        coordinates = np.column_stack(np.where(inverted > 0))
        deskew_angle: float | None = None
        if len(coordinates) >= 20:
            angle = float(cv2.minAreaRect(coordinates)[-1])
            angle = -(90 + angle) if angle < -45 else -angle
            if abs(angle) <= 15:
                deskew_angle = round(angle, 3)
                if abs(angle) >= 0.1:
                    height, width = array.shape[:2]
                    matrix = cv2.getRotationMatrix2D(
                        (width / 2, height / 2),
                        angle,
                        1.0,
                    )
                    array = cv2.warpAffine(
                        array,
                        matrix,
                        (width, height),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
        if aggressive:
            array = cv2.adaptiveThreshold(
                array,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            array = cv2.morphologyEx(array, cv2.MORPH_OPEN, kernel)
        return Image.fromarray(array), deskew_angle, "opencv"

    @staticmethod
    async def remove_preprocessed_page(
        preprocessed: OCRPreprocessedPage,
        rendered: OCRRenderedPage,
    ) -> None:
        if preprocessed.image_path != rendered.image_path:
            await asyncio.to_thread(
                preprocessed.image_path.unlink,
                missing_ok=True,
            )
