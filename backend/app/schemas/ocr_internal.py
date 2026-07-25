"""Typed, provider-neutral OCR data used inside worker pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.ocr_job import OCRLanguageProfile
from app.models.ocr_page_result import OCRPageStatus
from app.schemas.base import ApiSchema


class OCRBoundingBox(ApiSchema):
    """Axis-aligned image-space coordinates in rendered pixels."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class OCRBlockData(ApiSchema):
    """One provider result before database persistence."""

    text: str = Field(min_length=1)
    normalised_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    polygon: list[list[float]] = Field(min_length=4, max_length=32)
    bbox: OCRBoundingBox
    provider_model: str = Field(min_length=1, max_length=255)
    recognition_profile: OCRLanguageProfile
    orientation: int = 0
    metadata: dict[str, Any] | None = None

    @field_validator("text", "normalised_text", "provider_model")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("OCR text fields must not be blank.")
        return normalized

    @field_validator("polygon")
    @classmethod
    def validate_polygon(
        cls,
        value: list[list[float]],
    ) -> list[list[float]]:
        if any(len(point) != 2 or point[0] < 0 or point[1] < 0 for point in value):
            raise ValueError(
                "Each OCR polygon point must contain non-negative x and y."
            )
        return value

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("OCR orientation must be 0, 90, 180, or 270.")
        return value


class OCRPageResult(ApiSchema):
    """Complete result returned by one provider pipeline for one page."""

    page_number: int = Field(default=1, ge=1)
    status: OCRPageStatus = OCRPageStatus.COMPLETED
    language_profile: OCRLanguageProfile
    render_width: int = Field(default=0, ge=0)
    render_height: int = Field(default=0, ge=0)
    render_dpi: int = Field(default=300, ge=72)
    rotation_applied: int = 0
    deskew_angle: float | None = None
    blocks: list[OCRBlockData] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("rotation_applied")
    @classmethod
    def validate_rotation(cls, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("OCR rotation must be 0, 90, 180, or 270.")
        return value

    @model_validator(mode="after")
    def validate_failure_shape(self) -> OCRPageResult:
        if self.status is OCRPageStatus.FAILED and not self.error_code:
            raise ValueError("Failed OCR pages require an error code.")
        return self

    @property
    def raw_text(self) -> str:
        return "\n".join(block.text for block in self.blocks)

    @property
    def normalised_text(self) -> str:
        return "\n".join(block.normalised_text for block in self.blocks)


class OCRRenderedPage(ApiSchema):
    """Private rendered artifact passed only inside the worker."""

    page_number: int = Field(ge=1)
    image_path: Path
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    dpi: int = Field(ge=72)
    source_rotation: int = 0

    @field_validator("source_rotation")
    @classmethod
    def validate_source_rotation(cls, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("PDF source rotation must be 0, 90, 180, or 270.")
        return value


class OCRPreprocessedPage(ApiSchema):
    """Private preprocessed artifact plus applied transformations."""

    page_number: int = Field(ge=1)
    image_path: Path
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    rotation_applied: int = 0
    deskew_angle: float | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRPageSelection(ApiSchema):
    """Page-selection decision with explicit skipped-page provenance."""

    selected_page_numbers: list[int]
    skipped_page_numbers: list[int]
    selection_reasons: dict[str, str] = Field(default_factory=dict)


class OCRMergedBlock(ApiSchema):
    """Unified native/OCR view used by downstream language detection."""

    source: str
    source_id: str
    page_number: int = Field(ge=1)
    block_order: int = Field(ge=0)
    text: str
    normalised_text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)
