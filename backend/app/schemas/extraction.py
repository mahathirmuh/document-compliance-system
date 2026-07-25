"""Strict intermediate schemas shared by the Phase 6 extractors.

These models deliberately contain no database identifiers.  They are the
typed boundary between format-specific readers and the persistence layer.
"""

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PrivateAttr,
    model_validator,
)


class ExtractionResultStatus(StrEnum):
    """Terminal status produced by a format-specific extractor."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    OCR_REQUIRED = "OCR_REQUIRED"


class ExtractedContainerType(StrEnum):
    """Supported logical containers in the unified extraction model."""

    PDF_PAGE = "PDF_PAGE"
    DOCX_BODY = "DOCX_BODY"
    DOCX_HEADER = "DOCX_HEADER"
    DOCX_FOOTER = "DOCX_FOOTER"
    XLSX_WORKSHEET = "XLSX_WORKSHEET"


class ExtractedBlockType(StrEnum):
    """Supported block kinds in the unified extraction model."""

    TEXT = "TEXT"
    PARAGRAPH = "PARAGRAPH"
    HEADING = "HEADING"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    TABLE_CELL = "TABLE_CELL"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    WORKSHEET_TITLE = "WORKSHEET_TITLE"
    CELL = "CELL"
    MERGED_CELL = "MERGED_CELL"
    FORMULA = "FORMULA"
    PAGE_NUMBER = "PAGE_NUMBER"
    UNKNOWN = "UNKNOWN"


class ExtractionInternalModel(BaseModel):
    """Base configuration for trusted-but-strict intermediate data."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        strict=True,
        validate_assignment=True,
    )


ProgressCallback = Callable[[int, str], object]
CancellationChecker = Callable[[], object]


class ExtractionContext(ExtractionInternalModel):
    """Resource limits and safe-checkpoint callbacks supplied by a worker."""

    extraction_max_file_size_mb: Annotated[int, Field(ge=1, le=500)] = 50
    pdf_max_pages: Annotated[int, Field(ge=1, le=100_000)] = 5000
    pdf_min_characters_per_page: Annotated[int, Field(ge=0, le=1_000_000)] = 20
    pdf_scanned_page_ratio_threshold: Annotated[
        float,
        Field(gt=0.0, le=1.0),
    ] = 0.7
    docx_max_paragraphs: Annotated[int, Field(ge=1, le=10_000_000)] = 500_000
    docx_max_tables: Annotated[int, Field(ge=1, le=1_000_000)] = 10_000
    docx_max_table_cells: Annotated[
        int,
        Field(ge=1, le=100_000_000),
    ] = 2_000_000
    xlsx_max_worksheets: Annotated[int, Field(ge=1, le=10_000)] = 200
    xlsx_max_rows_per_sheet: Annotated[
        int,
        Field(ge=1, le=10_000_000),
    ] = 200_000
    xlsx_max_cells_per_workbook: Annotated[
        int,
        Field(ge=1, le=100_000_000),
    ] = 2_000_000
    xlsx_max_formulas: Annotated[int, Field(ge=0, le=100_000_000)] = 500_000
    progress_callback: ProgressCallback | None = Field(default=None, exclude=True)
    cancellation_checker: CancellationChecker | None = Field(
        default=None,
        exclude=True,
    )
    _last_reported_progress: int | None = PrivateAttr(default=None)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object] | None,
    ) -> Self:
        """Accept settings-style uppercase keys without weakening validation."""
        if value is None:
            return cls()

        source = dict(value)
        settings = source.pop("settings", None)
        normalized: dict[str, object] = {}
        for field_name in cls.model_fields:
            if settings is not None and hasattr(settings, field_name):
                normalized[field_name] = getattr(settings, field_name)

        for key, item in source.items():
            normalized[str(key).strip().lower()] = item
        return cls.model_validate(normalized)

    @property
    def maximum_file_size_bytes(self) -> int:
        """Return the configured file limit in bytes."""
        return self.extraction_max_file_size_mb * 1024 * 1024


class ExtractedBlockData(ExtractionInternalModel):
    """One searchable content unit in source order."""

    block_type: ExtractedBlockType
    block_order: Annotated[int, Field(ge=1)]
    source_reference: Annotated[str, Field(min_length=1, max_length=1000)]
    text: str
    normalised_text: str
    style_name: Annotated[str, Field(max_length=255)] | None = None
    heading_level: Annotated[int, Field(ge=1, le=9)] | None = None
    location: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    character_count: Annotated[int, Field(ge=0)]
    word_count: Annotated[int, Field(ge=0)]
    parent_block_order: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def validate_heading(self) -> Self:
        if (
            self.heading_level is not None
            and self.block_type is not ExtractedBlockType.HEADING
        ):
            raise ValueError("heading_level is only valid for HEADING blocks")
        return self


class ExtractedTableCellData(ExtractionInternalModel):
    """One logical DOCX table cell."""

    row_index: Annotated[int, Field(ge=1)]
    column_index: Annotated[int, Field(ge=1)]
    row_span: Annotated[int, Field(ge=1)] = 1
    column_span: Annotated[int, Field(ge=1)] = 1
    coordinate: Annotated[str, Field(max_length=100)] | None = None
    text: str
    normalised_text: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExtractedTableData(ExtractionInternalModel):
    """Structured representation of a table and its logical cells."""

    source_reference: Annotated[str, Field(min_length=1, max_length=1000)]
    table_index: Annotated[int, Field(ge=1)]
    row_count: Annotated[int, Field(ge=0)]
    column_count: Annotated[int, Field(ge=0)]
    raw_text: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    cells: list[ExtractedTableCellData] = Field(default_factory=list)


class ExtractedContainerData(ExtractionInternalModel):
    """A PDF page, DOCX logical part, or XLSX worksheet."""

    container_type: ExtractedContainerType
    container_index: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(max_length=500)] | None = None
    title: Annotated[str, Field(max_length=1000)] | None = None
    raw_text: str
    normalised_text: str
    character_count: Annotated[int, Field(ge=0)]
    word_count: Annotated[int, Field(ge=0)]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    blocks: list[ExtractedBlockData] = Field(default_factory=list)
    tables: list[ExtractedTableData] = Field(default_factory=list)


class ExtractedDocumentData(ExtractionInternalModel):
    """Complete normalized output from one format-specific extraction."""

    extractor_type: Literal["PDF", "DOCX", "XLSX"]
    extractor_version: Annotated[str, Field(min_length=1, max_length=50)] = "1.0.0"
    status: ExtractionResultStatus = ExtractionResultStatus.COMPLETED
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    containers: list[ExtractedContainerData] = Field(default_factory=list)
    warnings: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list,
    )
    requires_ocr: bool = False
    has_selectable_text: bool = True

    @model_validator(mode="after")
    def validate_ocr_status(self) -> Self:
        if self.status is ExtractionResultStatus.OCR_REQUIRED and not self.requires_ocr:
            raise ValueError("OCR_REQUIRED results must set requires_ocr")
        return self
