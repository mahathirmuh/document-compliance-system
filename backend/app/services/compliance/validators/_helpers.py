"""Shared evidence, rule, score, and result helpers for validators."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.compliance_internal import (
    ComplianceBlockData,
    ComplianceValidationContext,
    FindingDraft,
    ValidatorResult,
)
from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    float_value,
    int_value,
    mapping,
    option,
    read,
    string_list,
    string_value,
)
from app.services.compliance.constants import ValidatorStatus

_WEIGHT_FIELDS = {
    "DOCUMENT_CODE": "document_code_weight",
    "LANGUAGE_PRESENCE": "language_presence_weight",
    "LANGUAGE_COVERAGE": "language_coverage_weight",
    "REQUIRED_SECTIONS": "section_completeness_weight",
    "LANGUAGE_ORDER": "language_order_weight",
    "TRANSLATION_GROUPS": "translation_group_weight",
    "TABLE_MULTILINGUAL": "table_completeness_weight",
}

_ENABLED_FIELDS = {
    "DOCUMENT_CODE": "validate_document_code",
    "LANGUAGE_PRESENCE": "validate_language_presence",
    "LANGUAGE_COVERAGE": "validate_language_coverage",
    "CONTAINER_COMPLETENESS": "validate_container_completeness",
    "SECTION_DETECTION": "validate_sections",
    "REQUIRED_SECTIONS": "validate_sections",
    "SECTION_ORDER": "validate_sections",
    "LANGUAGE_ORDER": "validate_language_order",
    "TRANSLATION_GROUPS": "validate_translation_groups",
    "TABLE_MULTILINGUAL": "validate_tables",
    "CELL_MULTILINGUAL": "validate_cells",
}

_INELIGIBLE_TYPES = {"FORMULA", "PAGE_NUMBER"}
_INELIGIBLE_REASONS = {
    "EMPTY",
    "TOO_SHORT",
    "NO_LETTERS",
    "CODE_LIKE_TEXT",
    "URL_ONLY",
    "EMAIL_ONLY",
}


def validator_weight(
    context: ComplianceValidationContext,
    validator_code: str,
    *,
    scoring: bool = True,
) -> float:
    if not scoring:
        return 0.0
    field = _WEIGHT_FIELDS.get(validator_code)
    return float_value(read(context.rule, field or "", 0.0))


def validator_enabled(
    context: ComplianceValidationContext,
    validator_code: str,
) -> bool:
    field = _ENABLED_FIELDS.get(validator_code)
    return bool_value(read(context.rule, field or "", True), True)


def required_languages(
    context: ComplianceValidationContext,
) -> tuple[str, ...]:
    languages = string_list(
        read(context.rule, "required_languages", ("id", "en", "zh")),
    )
    return tuple(dict.fromkeys(language.casefold() for language in languages))


def required_sections(
    context: ComplianceValidationContext,
) -> tuple[str, ...]:
    sections = string_list(read(context.rule, "required_sections", ()))
    return tuple(dict.fromkeys(section.upper() for section in sections))


def expected_language_order(
    context: ComplianceValidationContext,
) -> tuple[str, ...]:
    configured = string_list(
        first(
            context.rule,
            "language_order",
            default=required_languages(context),
        ),
    )
    return tuple(
        dict.fromkeys(language.casefold() for language in configured)
    )


def eligible_block(
    block: object,
    *,
    minimum_confidence: float = 0.0,
) -> bool:
    block_type = enum_value(read(block, "block_type", "")).upper()
    if block_type in _INELIGIBLE_TYPES:
        return False
    eligibility = enum_value(
        read(block, "eligibility_status", "ELIGIBLE"),
    ).upper()
    if eligibility == "INELIGIBLE":
        return False
    metadata = mapping(read(block, "metadata", {}))
    reason = enum_value(
        first(
            metadata,
            "eligibility_reason",
            "eligibilityReason",
            default="",
        ),
    ).upper()
    if reason in _INELIGIBLE_REASONS:
        return False
    return float_value(read(block, "language_confidence", 0.0)) >= (
        minimum_confidence
    )


def block_characters(block: object) -> int:
    configured = int_value(read(block, "character_count", 0))
    if configured:
        return configured
    return len(string_value(first(block, "normalised_text", "text", default="")))


def result(
    validator_code: str,
    *,
    maximum_score: float,
    score: float,
    findings: Sequence[FindingDraft] = (),
    metrics: dict[str, object] | None = None,
    warnings: Sequence[str] = (),
    status: str | None = None,
    evaluated: bool = True,
) -> ValidatorResult:
    bounded_maximum = max(0.0, maximum_score)
    bounded_score = min(bounded_maximum, max(0.0, score))
    selected_status = status or ratio_status(
        bounded_score,
        bounded_maximum,
        evaluated=evaluated,
    )
    return ValidatorResult(
        validator_code=validator_code,
        status=selected_status,
        score=round(bounded_score, 4),
        maximum_score=round(bounded_maximum, 4),
        findings=list(findings),
        metrics=metrics or {},
        warnings=list(warnings),
    )


def skipped_result(
    context: ComplianceValidationContext,
    validator_code: str,
    *,
    scoring: bool = True,
) -> ValidatorResult:
    maximum = validator_weight(
        context,
        validator_code,
        scoring=scoring,
    )
    return result(
        validator_code,
        maximum_score=maximum,
        score=maximum,
        status=ValidatorStatus.SKIPPED,
        metrics={"enabled": False},
    )


def ratio_status(
    score: float,
    maximum_score: float,
    *,
    evaluated: bool = True,
) -> str:
    if not evaluated:
        return ValidatorStatus.NOT_EVALUATED
    if maximum_score <= 0:
        return ValidatorStatus.PASSED
    ratio = score / maximum_score
    if ratio >= 1.0:
        return ValidatorStatus.PASSED
    if ratio <= 0:
        return ValidatorStatus.FAILED
    return ValidatorStatus.PARTIAL


def context_option(
    context: ComplianceValidationContext,
    name: str,
    default: object,
) -> object:
    return option(context.rule, name, default)


def language_threshold(
    context: ComplianceValidationContext,
    field: str,
    language: str,
    default: float,
) -> float:
    configured = read(context.rule, field, None)
    values = mapping(configured)
    if values:
        return float_value(read(values, language, default), default)
    option_value = context_option(context, field, None)
    option_values = mapping(option_value)
    if option_values:
        return float_value(read(option_values, language, default), default)
    if option_value is not None:
        return float_value(option_value, default)
    return default


def finding_location(block: ComplianceBlockData | object) -> dict[str, object]:
    location = mapping(read(block, "location", {}))
    metadata = mapping(read(block, "metadata", {}))
    page = first(
        block,
        "page_number",
        default=first(location, "page", "pageNumber", default=None),
    )
    worksheet = first(
        metadata,
        "sheet",
        "worksheet",
        "worksheetName",
        default=read(block, "container_name", None),
    )
    coordinate = first(
        metadata,
        "coordinate",
        default=first(location, "coordinate", default=None),
    )
    return {
        "container_id": read(block, "container_id", None),
        "extracted_block_id": read(block, "id", None),
        "page_number": int_value(page) if page is not None else None,
        "worksheet_name": (
            string_value(worksheet) if worksheet is not None else None
        ),
        "cell_coordinate": (
            string_value(coordinate) if coordinate is not None else None
        ),
        "source_reference": string_value(
            read(block, "source_reference", ""),
        ),
        "location": location,
    }


def percentage(numerator: float, denominator: float) -> float:
    return (
        round(numerator * 100.0 / denominator, 4)
        if denominator > 0
        else 0.0
    )
