"""Typed, persistence-independent data exchanged by compliance services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.validation_options import normalize_validation_options


class ComplianceBlockData(ApiSchema):
    """Normalised source block used by all compliance validators."""

    id: UUID | None = None
    container_id: UUID | None = None
    container_type: str
    container_name: str | None = None
    container_index: int = Field(ge=0)
    block_order: int = Field(ge=0)
    block_type: str
    source_reference: str
    text: str
    normalised_text: str
    style_name: str | None = None
    heading_level: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, ge=1)
    language_code: str = "unknown"
    language_confidence: float = Field(default=0, ge=0, le=1)
    character_count: int = Field(default=0, ge=0)
    eligibility_status: str = "ELIGIBLE"
    location: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceContainerData(ApiSchema):
    """Logical validation container such as a page or worksheet."""

    id: UUID | None = None
    container_type: str
    container_name: str | None = None
    container_index: int = Field(ge=0)
    character_count: int = Field(default=0, ge=0)
    blocks: list[ComplianceBlockData] = Field(default_factory=list)


class ComplianceTableCellData(ApiSchema):
    """Language-aware source table cell."""

    id: UUID | None = None
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    coordinate: str | None = None
    text: str
    normalised_text: str
    language_code: str = "unknown"
    language_confidence: float = Field(default=0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceTableData(ApiSchema):
    """Extracted table supplied to grouping and table validators."""

    id: UUID | None = None
    container_id: UUID | None = None
    source_reference: str
    table_index: int = Field(ge=0)
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    cells: list[ComplianceTableCellData] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionAliasData(ApiSchema):
    """Flattened active alias consumed by the section matcher."""

    id: UUID | None = None
    profile_id: UUID | None = None
    section_definition_id: UUID | None = None
    canonical_code: str
    language_code: str
    alias_text: str
    normalised_alias: str | None = None
    match_type: str
    priority: int = Field(default=0, ge=0)
    is_regex: bool = False
    is_active: bool = True
    display_order: int = Field(default=0, ge=0)
    is_repeatable: bool = False


class DetectedSectionData(ApiSchema):
    """In-memory detected section before persistence."""

    section_definition_id: UUID | None = None
    canonical_code: str
    container_id: UUID | None = None
    heading_block_id: UUID | None = None
    heading_text: str
    heading_language_code: str | None = None
    match_type: str
    match_confidence: float = Field(ge=0, le=1)
    section_order: int = Field(ge=0)
    start_block_order: int = Field(ge=0)
    end_block_order: int = Field(ge=0)
    start_block_id: UUID | None = None
    end_block_id: UUID | None = None
    source_reference: str | None = None
    is_required: bool = False
    is_complete: bool = True
    language_presence: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class TranslationGroupMemberData(ApiSchema):
    """In-memory structural-group member."""

    block_id: UUID | None = None
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    language_block_result_id: UUID | None = None
    language_code: str
    block_order: int = Field(ge=0)
    text_snapshot: str
    confidence: float = Field(ge=0, le=1)
    source_reference: str
    source_type: str | None = None
    position: dict[str, Any] = Field(default_factory=dict)


class TranslationGroupData(ApiSchema):
    """In-memory positional/structural language group."""

    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    group_index: int = Field(ge=0)
    group_type: str
    source_reference: str
    expected_languages: list[str] = Field(default_factory=list)
    detected_languages: list[str] = Field(default_factory=list)
    language_order: list[str] = Field(default_factory=list)
    members: list[TranslationGroupMemberData] = Field(default_factory=list)
    is_complete: bool
    is_order_valid: bool
    confidence: float = Field(ge=0, le=1)
    detected_section_code: str | None = None
    start_block_order: int = Field(default=0, ge=0)
    end_block_order: int = Field(default=0, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)


class FindingDraft(ApiSchema):
    """Validator-produced finding that has not been persisted."""

    finding_code: str
    finding_type: str
    severity: str
    status: str = "OPEN"
    title: str
    description: str
    recommendation: str | None = None
    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    detected_section_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "detected_section_code",
            "detectedSectionCode",
            "section_code",
            "sectionCode",
        ),
    )
    translation_group_id: UUID | None = None
    translation_group_signature: str | None = None
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    page_number: int | None = Field(default=None, ge=1)
    worksheet_name: str | None = None
    cell_coordinate: str | None = None
    source_reference: str | None = None
    location: dict[str, Any] = Field(default_factory=dict)
    language_code: str | None = None
    expected_value: dict[str, Any] | list[Any] | None = None
    actual_value: dict[str, Any] | list[Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    is_system_generated: bool = True
    deduplication_key: str | None = None
    is_repeat: bool = False
    previous_finding_id: UUID | None = None


class ValidationRuleSnapshot(ApiSchema):
    """Immutable rule values captured for one validation run."""

    rule_id: UUID | None = None
    rule_code: str
    rule_name: str | None = Field(default=None, min_length=1, max_length=150)
    rule_version: int = Field(default=1, ge=1)
    validate_document_code: bool = True
    validate_language_presence: bool = True
    validate_language_coverage: bool = True
    validate_container_completeness: bool = False
    validate_sections: bool = False
    validate_language_order: bool = True
    validate_translation_groups: bool = False
    validate_tables: bool = False
    validate_cells: bool = False
    required_languages: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)
    section_alias_profile_id: UUID | None = None
    language_order: list[str] = Field(default_factory=list)
    minimum_language_block_coverage: dict[str, float] = Field(
        default_factory=dict
    )
    minimum_language_character_coverage: dict[str, float] = Field(
        default_factory=dict
    )
    maximum_unknown_block_percentage: float = Field(default=10, ge=0, le=100)
    maximum_mixed_block_percentage: float = Field(default=20, ge=0, le=100)
    document_code_weight: float = Field(default=10, ge=0)
    language_presence_weight: float = Field(default=25, ge=0)
    language_coverage_weight: float = Field(default=15, ge=0)
    section_completeness_weight: float = Field(default=20, ge=0)
    language_order_weight: float = Field(default=10, ge=0)
    translation_group_weight: float = Field(default=15, ge=0)
    table_completeness_weight: float = Field(default=5, ge=0)
    critical_finding_score_cap: float = Field(default=69, ge=0, le=100)
    major_finding_penalty: float = Field(default=5, ge=0)
    minor_finding_penalty: float = Field(default=1, ge=0)
    compliant_score: float = Field(default=95, ge=0, le=100)
    partially_compliant_score: float = Field(default=70, ge=0, le=100)
    needs_review_score: float = Field(default=50, ge=0, le=100)
    fail_on_missing_required_language: bool = True
    fail_on_missing_required_section: bool = False
    fail_on_critical_finding: bool = True
    validation_options: dict[str, Any] = Field(default_factory=dict)

    _validation_options = field_validator(
        "validation_options",
        mode="before",
    )(normalize_validation_options)

    @property
    def maximum_score(self) -> float:
        """Return the configured sum without silently normalising it."""
        return sum(
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


class ComplianceValidationContext(ApiSchema):
    """Complete prerequisite-resolved input for pure validators."""

    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None
    extraction_run_id: UUID | None = None
    ocr_run_id: UUID | None = None
    language_detection_run_id: UUID | None = None
    document_code: str | None = None
    expected_document_code: str | None = None
    source_format: str
    source_content_hash: str | None = None
    blocks: list[ComplianceBlockData] = Field(default_factory=list)
    containers: list[ComplianceContainerData] = Field(default_factory=list)
    tables: list[ComplianceTableData] = Field(default_factory=list)
    rule: ValidationRuleSnapshot
    section_aliases: list[SectionAliasData] = Field(default_factory=list)
    detected_sections: list[DetectedSectionData] = Field(default_factory=list)
    translation_groups: list[TranslationGroupData] = Field(default_factory=list)
    prerequisites: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ValidatorResult(ApiSchema):
    """Side-effect-free result returned by one compliance validator."""

    validator_code: str
    status: str
    score: float = Field(ge=0)
    maximum_score: float = Field(ge=0)
    findings: list[FindingDraft] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
