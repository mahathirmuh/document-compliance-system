"""Page selection and isolated render/preprocess/recognition retries."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from app.models.extracted_container import ExtractedContainer
from app.models.extraction_run import ExtractionRun, ExtractorType
from app.models.ocr_job import (
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_page_result import OCRPageStatus
from app.schemas.ocr_internal import (
    OCRBoundingBox,
    OCRPageResult,
    OCRPageSelection,
)
from app.services.ocr.base_ocr_provider import (
    BaseOCRProvider,
    OCRCancelledError,
    OCRError,
    OCRProviderUnavailableError,
)
from app.services.ocr.ocr_preprocessing_service import (
    OCRPreprocessingService,
)
from app.services.ocr.ocr_render_service import OCRRenderService

CancellationChecker = Callable[[], bool | Awaitable[bool]]
StageCallback = Callable[[str], None | Awaitable[None]]


class OCRPageService:
    """Select only low/no-text pages and process one page at a time."""

    def __init__(
        self,
        provider: BaseOCRProvider,
        render_service: OCRRenderService,
        preprocessing_service: OCRPreprocessingService,
        *,
        selectable_text_minimum: int = 50,
        skip_pages_with_selectable_text: bool = True,
        maximum_pages: int = 500,
        maximum_page_retries: int = 1,
        low_confidence_threshold: float = 0.60,
        low_confidence_block_ratio: float = 0.50,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        self.provider = provider
        self.render_service = render_service
        self.preprocessing_service = preprocessing_service
        self.selectable_text_minimum = selectable_text_minimum
        self.skip_pages_with_selectable_text = skip_pages_with_selectable_text
        self.maximum_pages = maximum_pages
        self.maximum_page_retries = maximum_page_retries
        self.low_confidence_threshold = low_confidence_threshold
        self.low_confidence_block_ratio = low_confidence_block_ratio
        self.provider_options = dict(provider_options or {})

    def select_pages(
        self,
        extraction_run: ExtractionRun,
        containers: Sequence[ExtractedContainer],
        *,
        requested_page_numbers: list[int] | None,
        force: bool,
    ) -> OCRPageSelection:
        if extraction_run.extractor_type is not ExtractorType.PDF:
            raise OCRError(
                "OCR_UNSUPPORTED_FILE_TYPE",
                "OCR is supported only for PDF extraction runs.",
            )
        total_pages = extraction_run.total_pages
        if total_pages < 1:
            raise OCRError(
                "OCR_NO_PAGES_REQUIRED",
                "The extraction run contains no PDF pages.",
            )
        if requested_page_numbers and any(
            page < 1 or page > total_pages for page in requested_page_numbers
        ):
            raise OCRError(
                "OCR_PAGE_FAILED",
                "One or more requested OCR pages do not exist.",
            )

        characters = {
            int(container.container_index): int(container.character_count)
            for container in containers
            if 1 <= int(container.container_index) <= total_pages
        }
        metadata = extraction_run.metadata_json or {}
        scanned_values = metadata.get("scannedPages", [])
        scanned_pages = {
            int(page)
            for page in scanned_values
            if isinstance(page, int) and not isinstance(page, bool)
        }
        low_text_pages = {
            page
            for page in range(1, total_pages + 1)
            if characters.get(page, 0) < self.selectable_text_minimum
        }
        required_pages = scanned_pages | low_text_pages
        candidates = (
            set(requested_page_numbers)
            if requested_page_numbers is not None
            else required_pages
        )
        selected: list[int] = []
        skipped: list[int] = []
        reasons: dict[str, str] = {}
        for page in sorted(candidates):
            has_sufficient_text = (
                characters.get(page, 0) >= self.selectable_text_minimum
            )
            if (
                self.skip_pages_with_selectable_text
                and has_sufficient_text
                and not force
            ):
                skipped.append(page)
                reasons[str(page)] = "SUFFICIENT_SELECTABLE_TEXT"
                continue
            selected.append(page)
            reasons[str(page)] = (
                "MANUAL_FORCE"
                if force and requested_page_numbers is not None
                else (
                    "SCAN_DETECTOR" if page in scanned_pages else "LOW_SELECTABLE_TEXT"
                )
            )
        if len(selected) > self.maximum_pages:
            raise OCRError(
                "OCR_PAGE_FAILED",
                "The OCR request exceeds the configured page limit.",
                details={
                    "maximumPages": self.maximum_pages,
                    "requestedPages": len(selected),
                },
            )
        return OCRPageSelection(
            selected_page_numbers=selected,
            skipped_page_numbers=skipped,
            selection_reasons=reasons,
        )

    async def process_page(
        self,
        pdf_path: Path,
        page_number: int,
        output_directory: Path,
        *,
        language_profile: OCRLanguageProfile,
        preprocessing_profile: OCRPreprocessingProfile,
        cancellation_checker: CancellationChecker | None = None,
        stage_callback: StageCallback | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> OCRPageResult:
        await self._checkpoint(cancellation_checker)
        await self._report(
            stage_callback,
            f"Rendering PDF page {page_number}",
        )
        rendered = await self.render_service.render_page(
            pdf_path,
            page_number,
            output_directory,
        )
        preprocessed = None
        try:
            await self._checkpoint(cancellation_checker)
            await self._report(
                stage_callback,
                f"Preprocessing PDF page {page_number}",
            )
            preprocessed = await self.preprocessing_service.preprocess(
                rendered,
                preprocessing_profile,
            )
            last_error: OCRError | None = None
            for attempt in range(1, self.maximum_page_retries + 2):
                await self._checkpoint(cancellation_checker)
                await self._report(
                    stage_callback,
                    f"Recognising PDF page {page_number}",
                )
                try:
                    result = await self.provider.recognise_page(
                        preprocessed.image_path,
                        language_profile.value,
                        {
                            **self.provider_options,
                            **(provider_options or {}),
                            "page_number": page_number,
                            "render_width": rendered.width,
                            "render_height": rendered.height,
                            "render_dpi": rendered.dpi,
                            "rotation_applied": (preprocessed.rotation_applied),
                            "cancellation_checker": cancellation_checker,
                        },
                    )
                    result.page_number = page_number
                    self._scale_blocks_to_render(
                        result,
                        source_width=preprocessed.width,
                        source_height=preprocessed.height,
                        render_width=rendered.width,
                        render_height=rendered.height,
                    )
                    result.render_width = rendered.width
                    result.render_height = rendered.height
                    result.render_dpi = rendered.dpi
                    provider_rotation = result.rotation_applied
                    result.rotation_applied = (
                        preprocessed.rotation_applied + provider_rotation
                    ) % 360
                    result.deskew_angle = preprocessed.deskew_angle
                    result.metadata = {
                        **(result.metadata or {}),
                        "preprocessing": preprocessed.metadata,
                        "sourceRotation": rendered.source_rotation,
                        "preprocessingRotation": preprocessed.rotation_applied,
                        "providerRotation": provider_rotation,
                        "pageAttempt": attempt,
                    }
                    if preprocessed.metadata.get("resized") is True:
                        result.warning_codes = list(
                            dict.fromkeys(
                                [
                                    *result.warning_codes,
                                    "OCR_LOW_RESOLUTION",
                                ]
                            )
                        )
                    self._classify_confidence(result)
                    return result
                except OCRProviderUnavailableError:
                    raise
                except OCRError as exc:
                    last_error = exc
                    if exc.code in {
                        "OCR_MODEL_LOAD_FAILED",
                        "OCR_PROVIDER_UNAVAILABLE",
                    }:
                        raise
                    if attempt <= self.maximum_page_retries:
                        await asyncio.sleep(0)
            assert last_error is not None
            return self.failed_page_result(
                page_number,
                language_profile,
                rendered.width,
                rendered.height,
                rendered.dpi,
                last_error,
            )
        finally:
            if preprocessed is not None:
                await self.preprocessing_service.remove_preprocessed_page(
                    preprocessed,
                    rendered,
                )
            await self.render_service.remove_rendered_page(rendered.image_path)

    @staticmethod
    def _scale_blocks_to_render(
        result: OCRPageResult,
        *,
        source_width: int,
        source_height: int,
        render_width: int,
        render_height: int,
    ) -> None:
        if source_width == render_width and source_height == render_height:
            return
        scale_x = render_width / source_width
        scale_y = render_height / source_height
        for block in result.blocks:
            block.polygon = [
                [point[0] * scale_x, point[1] * scale_y] for point in block.polygon
            ]
            block.bbox = OCRBoundingBox(
                x=block.bbox.x * scale_x,
                y=block.bbox.y * scale_y,
                width=block.bbox.width * scale_x,
                height=block.bbox.height * scale_y,
            )

    def _classify_confidence(self, result: OCRPageResult) -> None:
        if not result.blocks:
            result.status = OCRPageStatus.NO_TEXT_FOUND
            return
        low_count = sum(
            block.confidence < self.low_confidence_threshold for block in result.blocks
        )
        if low_count / len(result.blocks) >= self.low_confidence_block_ratio:
            result.status = OCRPageStatus.LOW_CONFIDENCE
            result.warning_codes = list(
                dict.fromkeys([*result.warning_codes, "OCR_LOW_CONFIDENCE"])
            )
        else:
            result.status = OCRPageStatus.COMPLETED

    @staticmethod
    def failed_page_result(
        page_number: int,
        language_profile: OCRLanguageProfile,
        width: int,
        height: int,
        dpi: int,
        error: OCRError,
    ) -> OCRPageResult:
        return OCRPageResult(
            page_number=page_number,
            status=OCRPageStatus.FAILED,
            language_profile=language_profile,
            render_width=width,
            render_height=height,
            render_dpi=dpi,
            error_code=error.code,
            error_message=error.safe_message,
            metadata={"errorDetails": error.details},
        )

    @staticmethod
    async def _checkpoint(
        cancellation_checker: CancellationChecker | None,
    ) -> None:
        if cancellation_checker is None:
            return
        cancelled = cancellation_checker()
        if isinstance(cancelled, Awaitable):
            cancelled = await cancelled
        if cancelled:
            raise OCRCancelledError

    @staticmethod
    async def _report(
        callback: StageCallback | None,
        stage: str,
    ) -> None:
        if callback is None:
            return
        result = callback(stage)
        if isinstance(result, Awaitable):
            await result
