"""Conservative scan detection for PDFs with no selectable page text."""

from dataclasses import dataclass

from app.schemas.extraction import ExtractionResultStatus


@dataclass(frozen=True, slots=True)
class PDFPageScanEvidence:
    """Signals collected without attempting OCR."""

    page_number: int
    character_count: int
    text_block_count: int
    image_count: int
    largest_image_area_ratio: float


@dataclass(frozen=True, slots=True)
class PDFScanDetection:
    """Document-level interpretation of page scan evidence."""

    status: ExtractionResultStatus
    scanned_pages: tuple[int, ...]
    scanned_page_ratio: float

    @property
    def requires_ocr(self) -> bool:
        return bool(self.scanned_pages)


class PDFScanDetector:
    """Classify image-dominant low-text pages without reading their images."""

    _LARGE_IMAGE_AREA_RATIO = 0.5

    def __init__(
        self,
        *,
        minimum_characters_per_page: int,
        scanned_page_ratio_threshold: float,
    ) -> None:
        self.minimum_characters_per_page = minimum_characters_per_page
        self.scanned_page_ratio_threshold = scanned_page_ratio_threshold

    def detect(
        self,
        pages: list[PDFPageScanEvidence],
    ) -> PDFScanDetection:
        if not pages:
            return PDFScanDetection(
                status=ExtractionResultStatus.COMPLETED,
                scanned_pages=(),
                scanned_page_ratio=0.0,
            )

        scanned_pages = tuple(
            page.page_number
            for page in pages
            if page.character_count < self.minimum_characters_per_page
            and page.image_count > 0
            and (
                page.text_block_count == 0
                or page.largest_image_area_ratio >= self._LARGE_IMAGE_AREA_RATIO
            )
        )
        scanned_ratio = len(scanned_pages) / len(pages)
        if scanned_pages and scanned_ratio >= self.scanned_page_ratio_threshold:
            status = ExtractionResultStatus.OCR_REQUIRED
        elif scanned_pages:
            status = ExtractionResultStatus.PARTIALLY_COMPLETED
        else:
            status = ExtractionResultStatus.COMPLETED
        return PDFScanDetection(
            status=status,
            scanned_pages=scanned_pages,
            scanned_page_ratio=scanned_ratio,
        )


def scanned_pages_warning(page_numbers: tuple[int, ...]) -> str:
    """Build a stable, user-safe warning."""
    joined = ", ".join(str(page_number) for page_number in page_numbers)
    noun = "Page" if len(page_numbers) == 1 else "Pages"
    return f"{noun} {joined} may require OCR."
