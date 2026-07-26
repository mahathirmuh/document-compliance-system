"""Public Phase 9 glossary master-data and transfer contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.glossary_enums import (
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossaryScopeType,
    GlossaryTermSeverity,
    GlossaryTermType,
    GlossaryVariantType,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.finding import sanitize_optional_text, sanitize_required_text


class GlossaryImportMode(StrEnum):
    """Supported workbook confirmation behavior."""

    CREATE_ONLY = "CREATE_ONLY"
    UPSERT = "UPSERT"


class GlossaryProfileValues(ApiSchema):
    """Shared writable profile values."""

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    scope_type: GlossaryScopeType = GlossaryScopeType.GLOBAL
    department_id: UUID | None = None
    document_type_id: UUID | None = None
    is_default: bool = False
    is_active: bool = True

    _code = field_validator("code", mode="before")(sanitize_required_text)
    _name = field_validator("name", mode="before")(sanitize_required_text)
    _description = field_validator("description", mode="before")(
        sanitize_optional_text
    )

    @model_validator(mode="after")
    def scope_is_consistent(self) -> GlossaryProfileValues:
        if self.scope_type is GlossaryScopeType.GLOBAL:
            valid = self.department_id is None and self.document_type_id is None
        elif self.scope_type is GlossaryScopeType.DEPARTMENT:
            valid = (
                self.department_id is not None
                and self.document_type_id is None
            )
        elif self.scope_type is GlossaryScopeType.DOCUMENT_TYPE:
            valid = (
                self.department_id is None
                and self.document_type_id is not None
            )
        else:
            valid = (
                self.department_id is not None
                and self.document_type_id is not None
            )
        if not valid:
            raise ValueError(
                "Profile scope fields do not match scopeType."
            )
        return self


class GlossaryProfileCreate(GlossaryProfileValues):
    pass


class GlossaryProfileUpdate(ApiSchema):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    scope_type: GlossaryScopeType | None = None
    department_id: UUID | None = None
    document_type_id: UUID | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("code", "name", mode="before")
    @classmethod
    def required_when_present(cls, value: object) -> object:
        return (
            sanitize_required_text(value)
            if isinstance(value, str)
            else value
        )

    _description = field_validator("description", mode="before")(
        sanitize_optional_text
    )


class GlossaryProfileResponse(ApiSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    scope_type: GlossaryScopeType
    department_id: UUID | None
    document_type_id: UUID | None
    is_default: bool
    is_active: bool
    version: int = Field(ge=1)
    term_count: int = Field(default=0, ge=0)
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class GlossaryProfileListResponse(PaginationData[GlossaryProfileResponse]):
    pass


class GlossaryTermValues(ApiSchema):
    glossary_profile_id: UUID
    term_code: str = Field(min_length=1, max_length=100)
    concept_name: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    term_type: GlossaryTermType = GlossaryTermType.PREFERRED
    severity: GlossaryTermSeverity = GlossaryTermSeverity.MINOR
    is_case_sensitive: bool = False
    match_whole_word: bool = True
    allow_inflection: bool = False
    is_regex: bool = False
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=5000)

    _term_code = field_validator("term_code", mode="before")(
        sanitize_required_text
    )
    _concept_name = field_validator("concept_name", mode="before")(
        sanitize_required_text
    )
    _optional_text = field_validator(
        "description",
        "notes",
        mode="before",
    )(sanitize_optional_text)


class GlossaryTermCreate(GlossaryTermValues):
    pass


class GlossaryTermUpdate(ApiSchema):
    term_code: str | None = Field(default=None, min_length=1, max_length=100)
    concept_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    description: str | None = Field(default=None, max_length=5000)
    term_type: GlossaryTermType | None = None
    severity: GlossaryTermSeverity | None = None
    is_case_sensitive: bool | None = None
    match_whole_word: bool | None = None
    allow_inflection: bool | None = None
    is_regex: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("term_code", "concept_name", mode="before")
    @classmethod
    def required_when_present(cls, value: object) -> object:
        return (
            sanitize_required_text(value)
            if isinstance(value, str)
            else value
        )

    _optional_text = field_validator(
        "description",
        "notes",
        mode="before",
    )(sanitize_optional_text)


class GlossaryTranslationCreate(ApiSchema):
    language_code: GlossaryLanguageCode
    term_text: str = Field(min_length=1, max_length=500)
    is_preferred: bool = False
    is_forbidden: bool = False
    is_required: bool = False
    priority: int = Field(default=0, ge=0, le=1_000_000)
    usage_note: str | None = Field(default=None, max_length=5000)
    example_text: str | None = Field(default=None, max_length=5000)
    is_active: bool = True

    _term_text = field_validator("term_text", mode="before")(
        sanitize_required_text
    )
    _optional_text = field_validator(
        "usage_note",
        "example_text",
        mode="before",
    )(sanitize_optional_text)

    @model_validator(mode="after")
    def preferred_is_not_forbidden(self) -> GlossaryTranslationCreate:
        if self.is_preferred and self.is_forbidden:
            raise ValueError(
                "A translation cannot be preferred and forbidden."
            )
        return self


class GlossaryTranslationUpdate(ApiSchema):
    language_code: GlossaryLanguageCode | None = None
    term_text: str | None = Field(default=None, min_length=1, max_length=500)
    is_preferred: bool | None = None
    is_forbidden: bool | None = None
    is_required: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=1_000_000)
    usage_note: str | None = Field(default=None, max_length=5000)
    example_text: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @field_validator("term_text", mode="before")
    @classmethod
    def term_text_when_present(cls, value: object) -> object:
        return (
            sanitize_required_text(value)
            if isinstance(value, str)
            else value
        )

    _optional_text = field_validator(
        "usage_note",
        "example_text",
        mode="before",
    )(sanitize_optional_text)


class GlossaryVariantCreate(ApiSchema):
    variant_text: str = Field(min_length=1, max_length=500)
    variant_type: GlossaryVariantType
    is_allowed: bool = True
    is_active: bool = True

    _variant_text = field_validator("variant_text", mode="before")(
        sanitize_required_text
    )


class GlossaryVariantUpdate(ApiSchema):
    variant_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    variant_type: GlossaryVariantType | None = None
    is_allowed: bool | None = None
    is_active: bool | None = None

    @field_validator("variant_text", mode="before")
    @classmethod
    def variant_when_present(cls, value: object) -> object:
        return (
            sanitize_required_text(value)
            if isinstance(value, str)
            else value
        )


class GlossaryVariantResponse(ApiSchema):
    id: UUID
    glossary_translation_id: UUID
    variant_text: str
    normalised_variant: str
    variant_type: GlossaryVariantType
    is_allowed: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GlossaryTranslationResponse(ApiSchema):
    id: UUID
    glossary_term_id: UUID
    language_code: GlossaryLanguageCode
    term_text: str
    normalised_term: str
    is_preferred: bool
    is_forbidden: bool
    is_required: bool
    priority: int = Field(ge=0)
    usage_note: str | None
    example_text: str | None
    is_active: bool
    variants: list[GlossaryVariantResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class GlossaryTermResponse(ApiSchema):
    id: UUID
    glossary_profile_id: UUID
    profile_code: str | None = None
    term_code: str
    concept_name: str
    description: str | None
    term_type: GlossaryTermType
    severity: GlossaryTermSeverity
    is_case_sensitive: bool
    match_whole_word: bool
    allow_inflection: bool
    is_regex: bool
    is_active: bool
    notes: str | None
    translations: list[GlossaryTranslationResponse] = Field(
        default_factory=list
    )
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class GlossaryTermListResponse(PaginationData[GlossaryTermResponse]):
    pass


class GlossaryExceptionValues(ApiSchema):
    glossary_term_id: UUID
    scope_type: GlossaryExceptionScopeType
    department_id: UUID | None = None
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None
    section_definition_id: UUID | None = None
    language_code: GlossaryLanguageCode | None = None
    exception_type: GlossaryExceptionType
    reason: str = Field(min_length=1, max_length=5000)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True
    approved_by: UUID | None = None

    _reason = field_validator("reason", mode="before")(sanitize_required_text)

    @model_validator(mode="after")
    def validate_scope_and_dates(self) -> GlossaryExceptionValues:
        targets = {
            GlossaryExceptionScopeType.DEPARTMENT: "department_id",
            GlossaryExceptionScopeType.DOCUMENT: "document_id",
            GlossaryExceptionScopeType.DOCUMENT_REVISION: (
                "document_revision_id"
            ),
            GlossaryExceptionScopeType.DOCUMENT_FILE: "document_file_id",
            GlossaryExceptionScopeType.SECTION: "section_definition_id",
        }
        populated = {
            name
            for name in (
                "department_id",
                "document_id",
                "document_revision_id",
                "document_file_id",
                "section_definition_id",
            )
            if getattr(self, name) is not None
        }
        expected = (
            set()
            if self.scope_type is GlossaryExceptionScopeType.GLOBAL
            else {targets[self.scope_type]}
        )
        if populated != expected:
            raise ValueError("The selected exception scope requires its ID.")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effectiveTo must not precede effectiveFrom.")
        return self


class GlossaryExceptionCreate(GlossaryExceptionValues):
    pass


class GlossaryExceptionUpdate(ApiSchema):
    scope_type: GlossaryExceptionScopeType | None = None
    department_id: UUID | None = None
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None
    section_definition_id: UUID | None = None
    language_code: GlossaryLanguageCode | None = None
    exception_type: GlossaryExceptionType | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=5000)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None
    approved_by: UUID | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def reason_when_present(cls, value: object) -> object:
        return (
            sanitize_required_text(value)
            if isinstance(value, str)
            else value
        )


class GlossaryExceptionResponse(ApiSchema):
    id: UUID
    glossary_term_id: UUID
    term_code: str | None = None
    scope_type: GlossaryExceptionScopeType
    department_id: UUID | None
    document_id: UUID | None
    document_revision_id: UUID | None
    document_file_id: UUID | None
    section_definition_id: UUID | None
    language_code: GlossaryLanguageCode | None
    exception_type: GlossaryExceptionType
    reason: str
    effective_from: date | None
    effective_to: date | None
    is_active: bool
    is_effective: bool
    is_expired: bool
    approved_by: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class GlossaryExceptionListResponse(
    PaginationData[GlossaryExceptionResponse]
):
    pass


class GlossaryTestMatchRequest(ApiSchema):
    text: str = Field(min_length=1, max_length=20_000)
    language_code: GlossaryLanguageCode
    profile_ids: list[UUID] = Field(default_factory=list, max_length=100)
    department_id: UUID | None = None
    document_type_id: UUID | None = None

    _text = field_validator("text", mode="before")(sanitize_required_text)

    @field_validator("profile_ids")
    @classmethod
    def deduplicate_profiles(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class GlossaryTestMatchOccurrence(ApiSchema):
    glossary_term_id: UUID
    glossary_translation_id: UUID | None
    glossary_variant_id: UUID | None
    term_code: str
    concept_name: str
    language_code: GlossaryLanguageCode
    matched_text: str
    normalised_matched_text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    match_type: GlossaryMatchType
    is_preferred: bool
    is_forbidden: bool
    is_allowed_variant: bool
    exception_applied: bool = False
    exception_id: UUID | None = None
    exception_type: GlossaryExceptionType | None = None


class GlossaryTestMatchResponse(ApiSchema):
    profile_ids: list[UUID]
    total_matches: int = Field(ge=0)
    matches: list[GlossaryTestMatchOccurrence]
    warnings: list[str] = Field(default_factory=list)


class GlossaryImportIssue(ApiSchema):
    sheet: str
    row_number: int = Field(ge=2)
    code: str
    field: str | None = None
    message: str


class GlossaryImportSheetSummary(ApiSchema):
    sheet: str
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)


class GlossaryImportPreviewResponse(ApiSchema):
    valid: bool
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    sheets: list[GlossaryImportSheetSummary]
    issues: list[GlossaryImportIssue]
    preview: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class GlossaryImportConfirmResponse(ApiSchema):
    mode: GlossaryImportMode
    total_rows: int = Field(ge=0)
    created: dict[str, int]
    updated: dict[str, int]
    skipped: dict[str, int]


class GlossaryArchiveResponse(ApiSchema):
    id: UUID
    is_active: Literal[False]


class GlossaryRestoreResponse(ApiSchema):
    id: UUID
    is_active: Literal[True]
