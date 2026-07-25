"""Validation-rule request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.validation_rule import (
    ALLOWED_SECTION_CODES,
    DEFAULT_LANGUAGE_ORDER,
    DEFAULT_REQUIRED_SECTIONS,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.department import normalize_description, normalize_name
from app.schemas.document_type import normalize_flexible_code
from app.schemas.master_data import MasterDataOption

SUPPORTED_LANGUAGES = frozenset({"id", "en", "zh"})


def normalize_language_order(value: list[str]) -> list[str]:
    normalized = [item.strip().lower() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Language order must not contain duplicates.")
    if any(item not in SUPPORTED_LANGUAGES for item in normalized):
        raise ValueError("Language order contains an unsupported language.")
    return normalized


def normalize_required_sections(value: list[str]) -> list[str]:
    normalized = [item.strip().upper() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Required sections must not contain duplicates.")
    invalid = sorted(set(normalized) - ALLOWED_SECTION_CODES)
    if invalid:
        raise ValueError(
            f"Required sections contain invalid codes: {', '.join(invalid)}."
        )
    return normalized


class ValidationRuleValues(ApiSchema):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=20)
    description: str | None = None
    document_type_id: UUID | None = None
    required_indonesian: bool = True
    required_english: bool = True
    required_chinese: bool = True
    minimum_indonesian_coverage: int = Field(default=95, ge=0, le=100)
    minimum_english_coverage: int = Field(default=95, ge=0, le=100)
    minimum_chinese_coverage: int = Field(default=95, ge=0, le=100)
    validate_language_order: bool = True
    language_order: list[str] = Field(
        default_factory=lambda: list(DEFAULT_LANGUAGE_ORDER)
    )
    validate_sections: bool = False
    required_sections: list[str] = Field(
        default_factory=lambda: list(DEFAULT_REQUIRED_SECTIONS)
    )
    validate_tables: bool = False
    minimum_compliance_score: int = Field(default=95, ge=0, le=100)
    partial_compliance_score: int = Field(default=70, ge=0, le=100)
    is_default: bool = False
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_flexible_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(
        normalize_description
    )
    _language_order = field_validator("language_order", mode="before")(
        normalize_language_order
    )
    _required_sections = field_validator("required_sections", mode="before")(
        normalize_required_sections
    )

    @model_validator(mode="after")
    def validate_business_rules(self) -> "ValidationRuleValues":
        if not (
            self.required_indonesian
            or self.required_english
            or self.required_chinese
        ):
            raise ValueError("At least one required language must be selected.")
        if self.partial_compliance_score > self.minimum_compliance_score:
            raise ValueError(
                "Partial compliance score must not exceed minimum "
                "compliance score."
            )
        if self.validate_language_order and not self.language_order:
            raise ValueError(
                "Language order must contain at least one supported language."
            )
        if self.is_default and not self.is_active:
            raise ValueError("A default validation rule must be active.")
        return self


class ValidationRuleCreate(ValidationRuleValues):
    pass


class ValidationRuleUpdate(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = None
    document_type_id: UUID | None = None
    required_indonesian: bool | None = None
    required_english: bool | None = None
    required_chinese: bool | None = None
    minimum_indonesian_coverage: int | None = Field(
        default=None, ge=0, le=100
    )
    minimum_english_coverage: int | None = Field(
        default=None, ge=0, le=100
    )
    minimum_chinese_coverage: int | None = Field(
        default=None, ge=0, le=100
    )
    validate_language_order: bool | None = None
    language_order: list[str] | None = None
    validate_sections: bool | None = None
    required_sections: list[str] | None = None
    validate_tables: bool | None = None
    minimum_compliance_score: int | None = Field(
        default=None, ge=0, le=100
    )
    partial_compliance_score: int | None = Field(
        default=None, ge=0, le=100
    )
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def validate_code(cls, value: object) -> object:
        return normalize_flexible_code(value) if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        return normalize_name(value) if isinstance(value, str) else value

    _description = field_validator("description", mode="before")(
        normalize_description
    )

    @field_validator("language_order", mode="before")
    @classmethod
    def validate_language_order_values(cls, value: object) -> object:
        return normalize_language_order(value) if isinstance(value, list) else value

    @field_validator("required_sections", mode="before")
    @classmethod
    def validate_required_section_values(cls, value: object) -> object:
        return normalize_required_sections(value) if isinstance(value, list) else value


class ValidationRuleResponse(ValidationRuleValues):
    id: UUID
    document_type: MasterDataOption | None = None
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ValidationRuleListResponse(PaginationData[ValidationRuleResponse]):
    pass


class ValidationRuleFilter(ApiSchema):
    document_type_id: UUID | None = None
    search: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "code"
    sort_order: str = "asc"
