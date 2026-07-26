"""Validation and normalization for flexible compliance-rule options."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

SECTION_COVERAGE_EVALUATION_MODES = frozenset(
    {
        "BOTH_REQUIRED",
        "EITHER_REQUIRED",
        "CHARACTER_ONLY",
        "BLOCK_ONLY",
    }
)
_SUPPORTED_LANGUAGES = frozenset({"id", "en", "zh"})
_DEFAULT_SECTION_KEYS = frozenset({"*", "DEFAULT"})


def normalize_validation_options(value: object) -> dict[str, object]:
    """Normalize known Phase 8 options while preserving future options.

    Section coverage is intentionally stored in ``validation_options_json``:
    the thresholds are optional and may differ by canonical section, while the
    flexible JSON contract keeps existing Phase 3 rules backward compatible.
    """

    if not isinstance(value, Mapping):
        raise ValueError(  # noqa: TRY004 - Pydantic validator contract
            "Validation options must be an object."
        )
    normalized = {str(key): item for key, item in value.items()}
    _normalize_alias(
        normalized,
        "validate_section_coverage",
        "validateSectionCoverage",
        _boolean_option,
    )
    _normalize_alias(
        normalized,
        "section_coverage_evaluation_mode",
        "sectionCoverageEvaluationMode",
        _coverage_mode,
    )
    _normalize_alias(
        normalized,
        "minimum_section_language_block_coverage",
        "minimumSectionLanguageBlockCoverage",
        _section_coverage_thresholds,
    )
    _normalize_alias(
        normalized,
        "minimum_section_language_character_coverage",
        "minimumSectionLanguageCharacterCoverage",
        _section_coverage_thresholds,
    )
    _normalize_alias(
        normalized,
        "section_coverage_minimum_confidence",
        "sectionCoverageMinimumConfidence",
        _confidence_option,
    )
    return normalized


def _normalize_alias(
    values: dict[str, object],
    snake_name: str,
    camel_name: str,
    normalizer: Callable[[object], object],
) -> None:
    has_snake = snake_name in values
    has_camel = camel_name in values
    if not has_snake and not has_camel:
        return
    if has_snake and has_camel and values[snake_name] != values[camel_name]:
        raise ValueError(f"Validation option {camel_name} was provided more than once.")
    raw = values[camel_name] if has_camel else values[snake_name]
    values.pop(snake_name, None)
    values.pop(camel_name, None)
    values[camel_name] = normalizer(raw)


def _boolean_option(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(  # noqa: TRY004 - Pydantic validator contract
            "validateSectionCoverage must be a boolean."
        )
    return value


def _coverage_mode(value: object) -> str:
    mode = str(value).strip().upper()
    if mode not in SECTION_COVERAGE_EVALUATION_MODES:
        allowed = ", ".join(sorted(SECTION_COVERAGE_EVALUATION_MODES))
        raise ValueError(f"sectionCoverageEvaluationMode must be one of: {allowed}.")
    return mode


def _confidence_option(value: object) -> float:
    numeric = _percentage(value, maximum=1)
    return numeric


def _section_coverage_thresholds(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(  # noqa: TRY004 - Pydantic validator contract
            "Section language coverage thresholds must be an object."
        )
    raw = {str(key): item for key, item in value.items()}
    if not raw:
        return {}
    if all(key.strip().casefold() in _SUPPORTED_LANGUAGES for key in raw):
        normalized_languages: dict[str, object] = {}
        normalized_languages.update(_language_thresholds(raw))
        return normalized_languages

    normalized: dict[str, object] = {}
    for section, language_values in raw.items():
        canonical = section.strip().upper()
        if not canonical:
            raise ValueError("Section coverage keys must not be empty.")
        if canonical not in _DEFAULT_SECTION_KEYS and (
            not canonical.replace("_", "").isalnum() or not canonical[0].isalpha()
        ):
            raise ValueError(
                f"Section coverage contains invalid section code: {section}."
            )
        if not isinstance(language_values, Mapping):
            raise ValueError(  # noqa: TRY004 - Pydantic validator contract
                "Each section coverage threshold must contain language percentages."
            )
        normalized[canonical] = _language_thresholds(language_values)
    return normalized


def _language_thresholds(value: Mapping[Any, object]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for language, percentage in value.items():
        code = str(language).strip().casefold()
        if code not in _SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Section coverage contains unsupported language: {language}."
            )
        normalized[code] = _percentage(percentage, maximum=100)
    return normalized


def _percentage(value: object, *, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(  # noqa: TRY004 - Pydantic validator contract
            "Section coverage thresholds must be numeric."
        )
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Section coverage thresholds must be numeric.") from exc
    if not 0 <= numeric <= maximum:
        raise ValueError(f"Section coverage values must be between 0 and {maximum}.")
    return numeric
