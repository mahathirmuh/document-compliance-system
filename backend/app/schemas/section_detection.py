"""Public schemas for section catalog management and detected sections."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator, model_validator

from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
    SectionLanguagePresenceStatus,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.master_data import ImportMode

_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]*$")


def _nonempty(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ValueError("Value must not be empty.")
    return normalized


def _code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Code must start with a letter and contain only letters, "
            "numbers, underscores, or hyphens."
        )
    return normalized


class SectionAliasProfileValues(ApiSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_default: bool = False
    is_active: bool = True

    _normalize_code = field_validator("code", mode="before")(_code)
    _normalize_name = field_validator("name", mode="before")(_nonempty)


class SectionAliasProfileCreate(SectionAliasProfileValues):
    pass


class SectionAliasProfileUpdate(ApiSchema):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return _code(value) if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return _nonempty(value) if isinstance(value, str) else value


class SectionAliasProfileResponse(SectionAliasProfileValues):
    id: UUID
    definition_count: int = Field(default=0, ge=0)
    alias_count: int = Field(default=0, ge=0)
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SectionAliasProfileListResponse(PaginationData[SectionAliasProfileResponse]):
    pass


class SectionDefinitionValues(ApiSchema):
    canonical_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_required_default: bool = False
    is_repeatable: bool = False
    is_active: bool = True

    _normalize_code = field_validator("canonical_code", mode="before")(_code)
    _normalize_name = field_validator("display_name", mode="before")(_nonempty)


class SectionDefinitionCreate(SectionDefinitionValues):
    profile_id: UUID


class SectionDefinitionUpdate(ApiSchema):
    canonical_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    description: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_required_default: bool | None = None
    is_repeatable: bool | None = None
    is_active: bool | None = None

    @field_validator("canonical_code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return _code(value) if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return _nonempty(value) if isinstance(value, str) else value


class SectionDefinitionResponse(SectionDefinitionValues):
    id: UUID
    profile_id: UUID
    alias_count: int = Field(default=0, ge=0)
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SectionDefinitionListResponse(PaginationData[SectionDefinitionResponse]):
    pass


class SectionAliasValues(ApiSchema):
    language_code: SectionAliasLanguageCode
    alias_text: str = Field(min_length=1, max_length=500)
    match_type: SectionAliasMatchType = SectionAliasMatchType.EXACT
    priority: int = Field(default=0, ge=0, le=10_000)
    is_regex: bool = False
    is_active: bool = True

    _normalize_alias = field_validator("alias_text", mode="before")(_nonempty)

    @model_validator(mode="after")
    def validate_regex_flags(self) -> Self:
        if self.is_regex != (self.match_type is SectionAliasMatchType.REGEX):
            raise ValueError("isRegex must be true exactly when matchType is REGEX.")
        return self


class SectionAliasCreate(SectionAliasValues):
    section_definition_id: UUID


class SectionAliasUpdate(ApiSchema):
    language_code: SectionAliasLanguageCode | None = None
    alias_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    match_type: SectionAliasMatchType | None = None
    priority: int | None = Field(default=None, ge=0, le=10_000)
    is_regex: bool | None = None
    is_active: bool | None = None

    @field_validator("alias_text", mode="before")
    @classmethod
    def normalize_alias(cls, value: object) -> object:
        return _nonempty(value) if isinstance(value, str) else value


class SectionAliasResponse(SectionAliasValues):
    id: UUID
    section_definition_id: UUID
    profile_id: UUID
    canonical_code: str
    display_name: str
    normalised_alias: str
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SectionAliasListResponse(PaginationData[SectionAliasResponse]):
    pass


class SectionDefinitionFilter(ApiSchema):
    profile_id: UUID | None = None
    search: str | None = None
    is_active: bool | None = None
    is_required_default: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    sort_by: str = "displayOrder"
    sort_order: str = "asc"


class SectionAliasFilter(ApiSchema):
    profile_id: UUID | None = None
    section_definition_id: UUID | None = None
    language_code: SectionAliasLanguageCode | None = None
    match_type: SectionAliasMatchType | None = None
    search: str | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    sort_by: str = "priority"
    sort_order: str = "desc"


class SectionMatchTestRequest(ApiSchema):
    heading: str = Field(
        min_length=1,
        max_length=10_000,
        validation_alias=AliasChoices("headingText", "heading"),
        serialization_alias="headingText",
    )
    profile_id: UUID | None = None
    language_code: SectionAliasLanguageCode | None = None

    _heading = field_validator("heading", mode="before")(_nonempty)


class SectionMatchTestResponse(ApiSchema):
    matched: bool
    profile_id: UUID | None = None
    section_definition_id: UUID | None = None
    canonical_code: str | None = None
    display_name: str | None = None
    language_code: SectionAliasLanguageCode | None = None
    matched_alias: str | None = None
    match_type: SectionAliasMatchType | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    normalized_heading: str = Field(
        validation_alias=AliasChoices(
            "normalisedHeading",
            "normalizedHeading",
            "normalized_heading",
        ),
        serialization_alias="normalisedHeading",
    )
    requires_review: bool = False


class SectionDefinitionImportRow(SectionDefinitionValues):
    row_number: int = Field(ge=2)


class SectionAliasImportRow(SectionAliasValues):
    row_number: int = Field(ge=2)
    canonical_code: str = Field(min_length=1, max_length=64)

    _canonical_code = field_validator("canonical_code", mode="before")(_code)


class SectionAliasImportError(ApiSchema):
    sheet: str
    row_number: int = Field(ge=1)
    field: str | None = None
    message: str


class SectionAliasImportPreview(ApiSchema):
    profile_id: UUID
    definitions: list[SectionDefinitionImportRow] = Field(default_factory=list)
    aliases: list[SectionAliasImportRow] = Field(default_factory=list)
    errors: list[SectionAliasImportError] = Field(default_factory=list)
    valid: bool


class SectionAliasImportResult(ApiSchema):
    profile_id: UUID
    definitions_created: int = Field(default=0, ge=0)
    definitions_updated: int = Field(default=0, ge=0)
    aliases_created: int = Field(default=0, ge=0)
    aliases_updated: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)


class SectionAliasImportPreviewRow(ApiSchema):
    """One frontend-facing row in a section-alias import preview."""

    sheet_name: Literal["Section Definitions", "Section Aliases"]
    row_number: int = Field(ge=2)
    status: Literal["VALID", "INVALID", "DUPLICATE"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SectionAliasImportTokenResponse(ApiSchema):
    """Bounded preview plus a short-lived, user-bound confirmation token."""

    import_token: str
    definitions: int = Field(ge=0)
    aliases: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    rows: list[SectionAliasImportPreviewRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SectionAliasImportConfirmRequest(ApiSchema):
    import_token: str = Field(min_length=1, max_length=8_000_000)
    mode: ImportMode = ImportMode.CREATE_ONLY


class SectionAliasImportConfirmResponse(ApiSchema):
    total_rows: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


class SectionLanguageResultResponse(ApiSchema):
    id: UUID
    detected_section_id: UUID
    language_code: str
    presence_status: SectionLanguagePresenceStatus
    block_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0, le=100)
    average_confidence: float | None = Field(default=None, ge=0, le=1)
    first_block_id: UUID | None
    last_block_id: UUID | None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DetectedSectionResponse(ApiSchema):
    id: UUID
    compliance_run_id: UUID
    section_definition_id: UUID | None
    canonical_code: str
    container_id: UUID | None
    start_block_id: UUID | None
    end_block_id: UUID | None
    heading_block_id: UUID | None
    heading_text: str
    heading_language_code: str | None
    match_type: SectionAliasMatchType
    match_confidence: float = Field(ge=0, le=1)
    section_order: int = Field(ge=0)
    is_required: bool
    is_complete: bool
    language_presence: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    language_results: list[SectionLanguageResultResponse] = Field(default_factory=list)
    finding_count: int = Field(default=0, ge=0)
    created_at: datetime


class DetectedSectionListResponse(PaginationData[DetectedSectionResponse]):
    pass
