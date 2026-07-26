"""Required canonical-section content and language completeness."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    DetectedSectionData,
    ValidatorResult,
)
from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    float_value,
    mapping,
)
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    MISSING_SECTION_LANGUAGE_CODES,
    FindingCode,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.sections.section_boundary_service import (
    section_content_blocks,
)
from app.services.compliance.validators._helpers import (
    block_characters,
    eligible_block,
    percentage,
    required_languages,
    required_sections,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


@dataclass(frozen=True)
class _LanguageCheck:
    presence_status: str
    block_coverage: float
    character_coverage: float
    minimum_block_coverage: float
    minimum_character_coverage: float
    coverage_ratio: float
    coverage_required: bool
    coverage_passed: bool

    @property
    def passed(self) -> bool:
        return (
            self.presence_status == "PRESENT"
            and (not self.coverage_required or self.coverage_passed)
        )


@dataclass(frozen=True)
class _SectionCheck:
    section: DetectedSectionData
    has_content: bool
    languages: dict[str, _LanguageCheck]

    @property
    def complete(self) -> bool:
        return self.has_content and all(
            check.passed for check in self.languages.values()
        )

    @property
    def failed_languages(self) -> list[str]:
        return [
            language
            for language, check in self.languages.items()
            if not check.passed
        ]


class RequiredSectionValidator(BaseComplianceValidator):
    code = "REQUIRED_SECTIONS"
    name = "Required sections"
    weight = 20.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        required = required_sections(context)
        languages = required_languages(context)
        if not required:
            return result(
                self.code,
                maximum_score=maximum,
                score=maximum,
                status="SKIPPED",
                metrics={"requiredSections": []},
            )
        by_code: dict[str, list[DetectedSectionData]] = defaultdict(list)
        for section in context.detected_sections:
            by_code[section.canonical_code.upper()].append(section)

        complete_count = 0
        generated = []
        section_metrics: list[dict[str, object]] = []
        fail_missing_section = context.rule.fail_on_missing_required_section
        options = mapping(context.rule.validation_options)
        coverage_enabled = bool_value(
            first(
                options,
                "validate_section_coverage",
                "validateSectionCoverage",
                default=False,
            ),
        )
        coverage_mode = enum_value(
            first(
                options,
                "section_coverage_evaluation_mode",
                "sectionCoverageEvaluationMode",
                default="BOTH_REQUIRED",
            ),
        ).upper()
        coverage_minimum_confidence = float_value(
            first(
                options,
                "section_coverage_minimum_confidence",
                "sectionCoverageMinimumConfidence",
                default=first(
                    options,
                    "coverage_minimum_confidence",
                    "coverageMinimumConfidence",
                    default=0.0,
                ),
            ),
        )
        for canonical in required:
            instances = by_code.get(canonical, [])
            if not instances:
                generated.append(
                    self.findings.create(
                        FindingCode.MISSING_REQUIRED_SECTION,
                        severity=(
                            FindingSeverity.CRITICAL
                            if fail_missing_section
                            else FindingSeverity.MAJOR
                        ),
                        detected_section_code=canonical,
                        description=(
                            f"Required section {canonical} was not detected."
                        ),
                        expected_value={"canonicalSection": canonical},
                        actual_value={"detected": False},
                    ),
                )
                section_metrics.append(
                    {
                        "canonicalCode": canonical,
                        "detected": False,
                        "complete": False,
                        "missingLanguages": list(languages),
                    },
                )
                continue

            checks = [
                self._check_section(
                    section,
                    context,
                    languages,
                    coverage_enabled=coverage_enabled,
                    coverage_mode=coverage_mode,
                    minimum_confidence=coverage_minimum_confidence,
                )
                for section in instances
            ]
            best = max(checks, key=self._section_rank)
            if best.complete:
                complete_count += 1
            for language in best.failed_languages:
                check = best.languages[language]
                coverage_failure = (
                    check.presence_status == "PRESENT"
                    and check.coverage_required
                    and not check.coverage_passed
                )
                severity = (
                    FindingSeverity.MAJOR
                    if not coverage_failure or check.coverage_ratio < 0.5
                    else FindingSeverity.MINOR
                )
                generated.append(
                    self.findings.create(
                        MISSING_SECTION_LANGUAGE_CODES.get(
                            language,
                            f"MISSING_SECTION_{language.upper()}",
                        ),
                        severity=severity,
                        language_code=language,
                        detected_section_code=canonical,
                        container_id=best.section.container_id,
                        source_reference=best.section.source_reference,
                        description=(
                            (
                                f"Required section {canonical} has "
                                f"{LANGUAGE_NAMES.get(language, language)} "
                                "coverage below the configured threshold."
                            )
                            if coverage_failure
                            else (
                                f"Required section {canonical} lacks "
                                f"{LANGUAGE_NAMES.get(language, language)} "
                                "evidence."
                            )
                        ),
                        expected_value={
                            "canonicalSection": canonical,
                            "requiredLanguage": language,
                            "minimumBlockCoverage": (
                                check.minimum_block_coverage
                            ),
                            "minimumCharacterCoverage": (
                                check.minimum_character_coverage
                            ),
                            "evaluationMode": coverage_mode,
                        },
                        actual_value={
                            "presenceStatus": check.presence_status,
                            "coverageStatus": (
                                "BELOW_THRESHOLD"
                                if coverage_failure
                                else "NOT_EVALUATED"
                            ),
                            "blockCoverage": check.block_coverage,
                            "characterCoverage": (
                                check.character_coverage
                            ),
                        },
                        metrics={
                            "coverageRatio": round(
                                check.coverage_ratio,
                                6,
                            ),
                            "coverageRequired": check.coverage_required,
                        },
                    ),
                )
            section_metrics.append(
                {
                    "canonicalCode": canonical,
                    "detected": True,
                    "complete": best.complete,
                    "hasContent": best.has_content,
                    "missingLanguages": [
                        language
                        for language, check in best.languages.items()
                        if check.presence_status != "PRESENT"
                    ],
                    "coverageBelowThresholdLanguages": [
                        language
                        for language, check in best.languages.items()
                        if check.presence_status == "PRESENT"
                        and check.coverage_required
                        and not check.coverage_passed
                    ],
                    "languageCoverage": {
                        language: {
                            "presenceStatus": check.presence_status,
                            "blockCoverage": check.block_coverage,
                            "characterCoverage": (
                                check.character_coverage
                            ),
                            "minimumBlockCoverage": (
                                check.minimum_block_coverage
                            ),
                            "minimumCharacterCoverage": (
                                check.minimum_character_coverage
                            ),
                            "coverageRatio": round(
                                check.coverage_ratio,
                                6,
                            ),
                            "coverageRequired": (
                                check.coverage_required
                            ),
                            "coveragePassed": check.coverage_passed,
                        }
                        for language, check in best.languages.items()
                    },
                    "instanceCount": len(instances),
                },
            )
        earned = complete_count / len(required) * maximum
        return result(
            self.code,
            maximum_score=maximum,
            score=earned,
            findings=generated,
            metrics={
                "requiredSections": list(required),
                "completeSections": complete_count,
                "totalRequiredSections": len(required),
                "sectionCoverageEnabled": coverage_enabled,
                "sectionCoverageEvaluationMode": coverage_mode,
                "sectionCoverageMinimumConfidence": (
                    coverage_minimum_confidence
                ),
                "sections": section_metrics,
            },
        )

    def _check_section(
        self,
        section: DetectedSectionData,
        context: ComplianceValidationContext,
        languages: tuple[str, ...],
        *,
        coverage_enabled: bool,
        coverage_mode: str,
        minimum_confidence: float,
    ) -> _SectionCheck:
        content = section_content_blocks(section, context.blocks)
        has_content = section.is_complete and bool(content)
        present = self._section_languages(section, content)
        eligible = [
            block
            for block in content
            if eligible_block(block, minimum_confidence=0.0)
        ]
        eligible_characters = sum(
            block_characters(block) for block in eligible
        )
        checks: dict[str, _LanguageCheck] = {}
        for language in languages:
            minimum_blocks = self._section_threshold(
                context.rule.validation_options,
                "minimum_section_language_block_coverage",
                section.canonical_code,
                language,
            )
            minimum_characters = self._section_threshold(
                context.rule.validation_options,
                "minimum_section_language_character_coverage",
                section.canonical_code,
                language,
            )
            language_blocks = [
                block
                for block in eligible
                if block.language_code.casefold() == language
                and block.language_confidence >= minimum_confidence
            ]
            block_coverage = percentage(
                len(language_blocks),
                len(eligible),
            )
            character_coverage = percentage(
                sum(block_characters(block) for block in language_blocks),
                eligible_characters,
            )
            coverage_required = coverage_enabled and (
                minimum_blocks > 0 or minimum_characters > 0
            )
            coverage_ratio, coverage_passed = self._coverage_result(
                block_coverage,
                character_coverage,
                minimum_blocks,
                minimum_characters,
                coverage_mode,
            )
            checks[language] = _LanguageCheck(
                presence_status=present.get(language, "NOT_PRESENT"),
                block_coverage=block_coverage,
                character_coverage=character_coverage,
                minimum_block_coverage=minimum_blocks,
                minimum_character_coverage=minimum_characters,
                coverage_ratio=coverage_ratio,
                coverage_required=coverage_required,
                coverage_passed=coverage_passed,
            )
        return _SectionCheck(
            section=section,
            has_content=has_content,
            languages=checks,
        )

    @staticmethod
    def _section_rank(check: _SectionCheck) -> tuple[object, ...]:
        return (
            check.complete,
            -len(check.failed_languages),
            sum(
                min(1.0, language.coverage_ratio)
                for language in check.languages.values()
            ),
            check.section.match_confidence,
        )

    @staticmethod
    def _section_threshold(
        options: object,
        option_name: str,
        canonical_code: str,
        language: str,
    ) -> float:
        configured = mapping(first(options, option_name, default={}))
        if not configured:
            return 0.0
        # A flat language map applies to every required section. A nested map
        # can set a DEFAULT/* baseline or a canonical-section override.
        if any(key.casefold() in {"id", "en", "zh"} for key in configured):
            language_values = configured
        else:
            language_values: dict[str, object] = {}
            for key in ("DEFAULT", "*", canonical_code.upper()):
                for configured_key, value in configured.items():
                    if configured_key.upper() == key:
                        language_values.update(mapping(value))
        return float_value(first(language_values, language, default=0.0))

    @staticmethod
    def _coverage_result(
        block_coverage: float,
        character_coverage: float,
        minimum_blocks: float,
        minimum_characters: float,
        mode: str,
    ) -> tuple[float, bool]:
        block_check = (
            (block_coverage / minimum_blocks, block_coverage >= minimum_blocks)
            if minimum_blocks > 0
            else None
        )
        character_check = (
            (
                character_coverage / minimum_characters,
                character_coverage >= minimum_characters,
            )
            if minimum_characters > 0
            else None
        )
        if mode == "BLOCK_ONLY":
            selected = [block_check] if block_check is not None else []
        elif mode == "CHARACTER_ONLY":
            selected = (
                [character_check] if character_check is not None else []
            )
        else:
            selected = [
                check
                for check in (block_check, character_check)
                if check is not None
            ]
        if not selected:
            return 1.0, True
        ratios = [check[0] for check in selected]
        passed = [check[1] for check in selected]
        if mode == "EITHER_REQUIRED":
            return max(ratios), any(passed)
        return min(ratios), all(passed)

    @staticmethod
    def _section_languages(
        section: DetectedSectionData,
        content: list[object],
    ) -> dict[str, str]:
        configured = mapping(section.language_presence)
        states = {
            str(language).casefold(): enum_value(status).upper()
            for language, status in configured.items()
        }
        if states:
            return states
        present = {
            str(getattr(block, "language_code", "unknown")).casefold()
            for block in content
            if eligible_block(block)
        }
        return {
            language: "PRESENT" for language in present
        }
