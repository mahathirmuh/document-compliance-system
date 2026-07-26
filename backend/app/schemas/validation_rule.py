"""Validation-rule request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator, model_validator

from app.models.validation_rule import (
    ALLOWED_SECTION_CODES,
    DEFAULT_LANGUAGE_BLOCK_COVERAGE,
    DEFAULT_LANGUAGE_CHARACTER_COVERAGE,
    DEFAULT_LANGUAGE_ORDER,
    DEFAULT_REQUIRED_LANGUAGES,
    DEFAULT_REQUIRED_SECTIONS,
    QualityScoreMode,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.department import normalize_description, normalize_name
from app.schemas.document_type import normalize_flexible_code
from app.schemas.master_data import MasterDataOption
from app.schemas.validation_options import normalize_validation_options

SUPPORTED_LANGUAGES = frozenset({"id", "en", "zh"})
_VALIDATION_RULE_EXPLICIT_FIELDS = "validation_rule_explicit_fields"
_LEGACY_REQUIRED_LANGUAGE_FIELDS = {
    "required_indonesian": "id",
    "required_english": "en",
    "required_chinese": "zh",
}
_LEGACY_COVERAGE_FIELDS = {
    "minimum_indonesian_coverage": "id",
    "minimum_english_coverage": "en",
    "minimum_chinese_coverage": "zh",
}


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


def normalize_required_languages(value: list[str]) -> list[str]:
    normalized = [item.strip().lower() for item in value]
    if not normalized:
        raise ValueError("At least one required language must be selected.")
    if len(normalized) != len(set(normalized)):
        raise ValueError("Required languages must not contain duplicates.")
    if any(item not in SUPPORTED_LANGUAGES for item in normalized):
        raise ValueError("Required languages contain an unsupported language.")
    return normalized


def normalize_coverage_map(value: dict[str, float]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for language, percentage in value.items():
        code = language.strip().lower()
        if code not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Coverage contains unsupported language: {language}.")
        numeric = float(percentage)
        if not 0 <= numeric <= 100:
            raise ValueError("Language coverage percentages must be between 0 and 100.")
        normalized[code] = numeric
    return normalized


class ValidationRuleValues(ApiSchema):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=20)
    description: str | None = None
    document_type_id: UUID | None = None
    required_indonesian: bool = True
    required_english: bool = True
    required_chinese: bool = True
    validate_document_code: bool = True
    validate_language_presence: bool = True
    validate_language_coverage: bool = True
    validate_container_completeness: bool = False
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
    validate_translation_groups: bool = False
    validate_cells: bool = False
    required_languages: list[str] = Field(
        default_factory=lambda: list(DEFAULT_REQUIRED_LANGUAGES)
    )
    section_alias_profile_id: UUID | None = None
    minimum_language_block_coverage: dict[str, float] = Field(
        default_factory=lambda: {
            language: float(coverage)
            for language, coverage in DEFAULT_LANGUAGE_BLOCK_COVERAGE.items()
        }
    )
    minimum_language_character_coverage: dict[str, float] = Field(
        default_factory=lambda: {
            language: float(coverage)
            for language, coverage in DEFAULT_LANGUAGE_CHARACTER_COVERAGE.items()
        }
    )
    maximum_unknown_block_percentage: float = Field(
        default=10,
        ge=0,
        le=100,
    )
    maximum_mixed_block_percentage: float = Field(
        default=20,
        ge=0,
        le=100,
    )
    document_code_weight: float = Field(default=10, ge=0, le=100)
    language_presence_weight: float = Field(default=25, ge=0, le=100)
    language_coverage_weight: float = Field(default=15, ge=0, le=100)
    section_completeness_weight: float = Field(default=20, ge=0, le=100)
    language_order_weight: float = Field(default=10, ge=0, le=100)
    translation_group_weight: float = Field(default=15, ge=0, le=100)
    table_completeness_weight: float = Field(default=5, ge=0, le=100)
    translation_similarity_weight: float = Field(
        default=25,
        ge=0,
        le=100,
    )
    glossary_compliance_weight: float = Field(
        default=15,
        ge=0,
        le=100,
    )
    quality_score_mode: QualityScoreMode = QualityScoreMode.SEPARATE_QUALITY_SCORE
    critical_finding_score_cap: float = Field(default=69, ge=0, le=100)
    major_finding_penalty: float = Field(default=5, ge=0, le=100)
    minor_finding_penalty: float = Field(default=1, ge=0, le=100)
    compliant_score: float = Field(default=95, ge=0, le=100)
    partially_compliant_score: float = Field(default=70, ge=0, le=100)
    needs_review_score: float = Field(default=50, ge=0, le=100)
    fail_on_missing_required_language: bool = True
    fail_on_missing_required_section: bool = False
    fail_on_critical_finding: bool = True
    validation_options: dict[str, object] = Field(default_factory=dict)
    minimum_compliance_score: int = Field(default=95, ge=0, le=100)
    partial_compliance_score: int = Field(default=70, ge=0, le=100)
    is_default: bool = False
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_flexible_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(normalize_description)
    _language_order = field_validator("language_order", mode="before")(
        normalize_language_order
    )
    _required_sections = field_validator("required_sections", mode="before")(
        normalize_required_sections
    )
    _required_languages = field_validator(
        "required_languages",
        mode="before",
    )(normalize_required_languages)
    _block_coverage = field_validator(
        "minimum_language_block_coverage",
        mode="before",
    )(normalize_coverage_map)
    _character_coverage = field_validator(
        "minimum_language_character_coverage",
        mode="before",
    )(normalize_coverage_map)
    _validation_options = field_validator(
        "validation_options",
        mode="before",
    )(normalize_validation_options)

    @model_validator(mode="after")
    def validate_business_rules(
        self,
        info: ValidationInfo,
    ) -> "ValidationRuleValues":
        explicit_fields = self._explicit_fields(info)
        if "required_languages" in explicit_fields:
            self.required_indonesian = "id" in self.required_languages
            self.required_english = "en" in self.required_languages
            self.required_chinese = "zh" in self.required_languages
        elif explicit_fields & _LEGACY_REQUIRED_LANGUAGE_FIELDS.keys():
            self.required_languages = [
                language
                for field, language in _LEGACY_REQUIRED_LANGUAGE_FIELDS.items()
                if getattr(self, field)
            ]
        if not self.required_languages:
            raise ValueError("At least one required language must be selected.")
        self._synchronize_coverages(explicit_fields)
        if "compliant_score" in explicit_fields:
            self.minimum_compliance_score = int(self.compliant_score)
        elif "minimum_compliance_score" in explicit_fields:
            self.compliant_score = float(self.minimum_compliance_score)
        if "partially_compliant_score" in explicit_fields:
            self.partial_compliance_score = int(self.partially_compliant_score)
        elif "partial_compliance_score" in explicit_fields:
            self.partially_compliant_score = float(self.partial_compliance_score)
        if self.partial_compliance_score > self.minimum_compliance_score:
            raise ValueError(
                "Partial compliance score must not exceed minimum compliance score."
            )
        if not (
            self.needs_review_score
            <= self.partially_compliant_score
            <= self.compliant_score
        ):
            raise ValueError(
                "Score thresholds must satisfy needsReviewScore <= "
                "partiallyCompliantScore <= compliantScore."
            )
        weight_total = sum(
            (
                self.document_code_weight,
                self.language_presence_weight,
                self.language_coverage_weight,
                self.section_completeness_weight,
                self.language_order_weight,
                self.translation_group_weight,
                self.table_completeness_weight,
            )
        )
        if abs(weight_total - 100) > 0.001:
            raise ValueError("Validation rule weights must total exactly 100.")
        if self.translation_similarity_weight + self.glossary_compliance_weight > 100:
            raise ValueError(
                "Translation similarity and glossary compliance weights "
                "must total 100 or less."
            )
        if self.validate_language_order and not self.language_order:
            raise ValueError(
                "Language order must contain at least one supported language."
            )
        if self.is_default and not self.is_active:
            raise ValueError("A default validation rule must be active.")
        return self

    def _synchronize_coverages(self, explicit_fields: set[str]) -> None:
        advanced_block = "minimum_language_block_coverage" in explicit_fields
        advanced_character = "minimum_language_character_coverage" in explicit_fields
        explicit_legacy = explicit_fields & _LEGACY_COVERAGE_FIELDS.keys()
        if advanced_block or advanced_character:
            # Block coverage is the Phase 3 mirror when both advanced
            # dimensions are supplied. Character-only payloads still update
            # the legacy mirror so advanced-only clients remain compatible.
            source = (
                self.minimum_language_block_coverage
                if advanced_block
                else self.minimum_language_character_coverage
            )
            for field, language in _LEGACY_COVERAGE_FIELDS.items():
                if language in source:
                    setattr(self, field, int(source[language]))
            return
        if not explicit_legacy:
            return
        block_coverage = dict(self.minimum_language_block_coverage)
        character_coverage = dict(self.minimum_language_character_coverage)
        for field in explicit_legacy:
            language = _LEGACY_COVERAGE_FIELDS[field]
            coverage = float(getattr(self, field))
            block_coverage[language] = coverage
            character_coverage[language] = coverage
        self.minimum_language_block_coverage = block_coverage
        self.minimum_language_character_coverage = character_coverage

    def _explicit_fields(self, info: ValidationInfo) -> set[str]:
        context = info.context
        if isinstance(context, dict):
            configured = context.get(_VALIDATION_RULE_EXPLICIT_FIELDS)
            if configured is not None:
                return {str(field) for field in configured}
        return set(self.model_fields_set)


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
    validate_document_code: bool | None = None
    validate_language_presence: bool | None = None
    validate_language_coverage: bool | None = None
    validate_container_completeness: bool | None = None
    minimum_indonesian_coverage: int | None = Field(default=None, ge=0, le=100)
    minimum_english_coverage: int | None = Field(default=None, ge=0, le=100)
    minimum_chinese_coverage: int | None = Field(default=None, ge=0, le=100)
    validate_language_order: bool | None = None
    language_order: list[str] | None = None
    validate_sections: bool | None = None
    required_sections: list[str] | None = None
    validate_tables: bool | None = None
    validate_translation_groups: bool | None = None
    validate_cells: bool | None = None
    required_languages: list[str] | None = None
    section_alias_profile_id: UUID | None = None
    minimum_language_block_coverage: dict[str, float] | None = None
    minimum_language_character_coverage: dict[str, float] | None = None
    maximum_unknown_block_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    maximum_mixed_block_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    document_code_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    language_presence_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    language_coverage_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    section_completeness_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    language_order_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    translation_group_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    table_completeness_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    translation_similarity_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    glossary_compliance_weight: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    quality_score_mode: QualityScoreMode | None = None
    critical_finding_score_cap: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    major_finding_penalty: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    minor_finding_penalty: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    compliant_score: float | None = Field(default=None, ge=0, le=100)
    partially_compliant_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    needs_review_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    fail_on_missing_required_language: bool | None = None
    fail_on_missing_required_section: bool | None = None
    fail_on_critical_finding: bool | None = None
    validation_options: dict[str, object] | None = None
    minimum_compliance_score: int | None = Field(default=None, ge=0, le=100)
    partial_compliance_score: int | None = Field(default=None, ge=0, le=100)
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

    _description = field_validator("description", mode="before")(normalize_description)

    @field_validator("language_order", mode="before")
    @classmethod
    def validate_language_order_values(cls, value: object) -> object:
        return normalize_language_order(value) if isinstance(value, list) else value

    @field_validator("required_sections", mode="before")
    @classmethod
    def validate_required_section_values(cls, value: object) -> object:
        return normalize_required_sections(value) if isinstance(value, list) else value

    @field_validator("required_languages", mode="before")
    @classmethod
    def validate_required_language_values(cls, value: object) -> object:
        return normalize_required_languages(value) if isinstance(value, list) else value

    @field_validator(
        "minimum_language_block_coverage",
        "minimum_language_character_coverage",
        mode="before",
    )
    @classmethod
    def validate_coverage_values(cls, value: object) -> object:
        return normalize_coverage_map(value) if isinstance(value, dict) else value

    @field_validator("validation_options", mode="before")
    @classmethod
    def validate_validation_options(cls, value: object) -> object:
        return None if value is None else normalize_validation_options(value)


class ValidationRuleResponse(ValidationRuleValues):
    id: UUID
    document_type: MasterDataOption | None = None
    section_alias_profile: MasterDataOption | None = None
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime

    def _explicit_fields(self, info: ValidationInfo) -> set[str]:
        """Responses reflect persisted mirrors without reinterpreting input."""

        del info
        return set()


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
