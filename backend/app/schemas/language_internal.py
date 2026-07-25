"""Typed intermediate contracts for Phase 7 language analysis."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityReason,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.schemas.base import ApiSchema


class UnicodeDominantScript(StrEnum):
    LATIN = "LATIN"
    HAN = "HAN"
    MIXED = "MIXED"
    NONE = "NONE"
    OTHER = "OTHER"


class LanguagePresenceState(StrEnum):
    PRESENT = "PRESENT"
    NOT_PRESENT = "NOT_PRESENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ScriptStatisticsData(ApiSchema):
    latin_character_count: int = Field(ge=0)
    han_character_count: int = Field(ge=0)
    digit_count: int = Field(ge=0)
    punctuation_count: int = Field(ge=0)
    symbol_count: int = Field(ge=0)
    other_letter_count: int = Field(ge=0)
    total_character_count: int = Field(ge=0)
    dominant_script: UnicodeDominantScript
    han_ratio: float = Field(ge=0, le=1)
    latin_ratio: float = Field(ge=0, le=1)


class LanguageEligibilityData(ApiSchema):
    status: LanguageEligibilityStatus
    reason: LanguageEligibilityReason | None = None

    @model_validator(mode="after")
    def validate_reason(self) -> LanguageEligibilityData:
        if (
            self.status is LanguageEligibilityStatus.ELIGIBLE
            and self.reason is not None
        ):
            raise ValueError("Eligible text must not contain a reason.")
        if (
            self.status is LanguageEligibilityStatus.INELIGIBLE
            and self.reason is None
        ):
            raise ValueError("Ineligible text must contain a reason.")
        return self


class LanguageScoreData(ApiSchema):
    language_code: LanguageCode
    score: float = Field(ge=0, le=1)


class LanguageDetectionData(ApiSchema):
    language_code: LanguageCode
    primary_language_code: LanguageCode
    confidence: float = Field(ge=0, le=1)
    is_mixed: bool
    detected_languages: list[LanguageScoreData] = Field(default_factory=list)
    script_statistics: ScriptStatisticsData
    eligibility: LanguageEligibilityData
    character_count: int = Field(ge=0)
    latin_character_count: int = Field(ge=0)
    han_character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class LanguageSourceBlockData(ApiSchema):
    """One native or OCR source with retained provenance."""

    source_type: LanguageSourceType
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    container_id: UUID | None = None
    container_type: str
    container_name: str | None = None
    container_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    block_order: int = Field(ge=0)
    source_reference: str
    text: str
    normalised_text: str
    source_confidence: float | None = Field(default=None, ge=0, le=1)
    source_metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> LanguageSourceBlockData:
        has_native = self.extracted_block_id is not None
        has_ocr = self.ocr_block_id is not None
        if has_native == has_ocr:
            raise ValueError("Exactly one source block identifier is required.")
        if (
            self.source_type is LanguageSourceType.NATIVE_EXTRACTION
            and not has_native
        ):
            raise ValueError("Native source requires extracted_block_id.")
        if self.source_type is LanguageSourceType.OCR and not has_ocr:
            raise ValueError("OCR source requires ocr_block_id.")
        return self


class DetectedLanguageBlockData(ApiSchema):
    source: LanguageSourceBlockData
    detection: LanguageDetectionData


class CoverageBreakdownData(ApiSchema):
    id: float = Field(ge=0, le=100)
    en: float = Field(ge=0, le=100)
    zh: float = Field(ge=0, le=100)
    mixed: float = Field(ge=0, le=100)
    unknown: float = Field(ge=0, le=100)
    other: float = Field(ge=0, le=100)


class LanguagePresenceData(ApiSchema):
    id: LanguagePresenceState
    en: LanguagePresenceState
    zh: LanguagePresenceState


class PreliminaryCoverageData(ApiSchema):
    block_coverage: CoverageBreakdownData
    character_coverage: CoverageBreakdownData
    language_presence: LanguagePresenceData
    preliminary: bool = True


class AggregatedLanguageData(ApiSchema):
    total_blocks: int = Field(ge=0)
    eligible_blocks: int = Field(ge=0)
    detected_blocks: int = Field(ge=0)
    unknown_blocks: int = Field(ge=0)
    mixed_blocks: int = Field(ge=0)
    indonesian_blocks: int = Field(ge=0)
    english_blocks: int = Field(ge=0)
    chinese_blocks: int = Field(ge=0)
    other_blocks: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    indonesian_characters: int = Field(ge=0)
    english_characters: int = Field(ge=0)
    chinese_characters: int = Field(ge=0)
    mixed_characters: int = Field(ge=0)
    unknown_characters: int = Field(ge=0)
    other_characters: int = Field(ge=0)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    dominant_language: LanguageCode
    coverage: PreliminaryCoverageData


class LanguageContainerAggregateData(ApiSchema):
    container_id: UUID | None = None
    container_type: str
    container_name: str | None = None
    container_index: int = Field(ge=0)
    aggregate: AggregatedLanguageData


class LanguagePipelineResultData(ApiSchema):
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocks: list[DetectedLanguageBlockData]
    containers: list[LanguageContainerAggregateData]
    aggregate: AggregatedLanguageData
    detector_name: str
    detector_version: str
    warnings: list[str] = Field(default_factory=list)
