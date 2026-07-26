"""Block/character coverage plus unknown and mixed review thresholds."""

from __future__ import annotations

from collections import defaultdict

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import (
    enum_value,
    float_value,
    read,
)
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    LOW_COVERAGE_CODES,
    FindingCode,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.validators._helpers import (
    block_characters,
    context_option,
    eligible_block,
    language_threshold,
    percentage,
    required_languages,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class LanguageCoverageValidator(BaseComplianceValidator):
    code = "LANGUAGE_COVERAGE"
    name = "Language coverage"
    weight = 15.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        languages = required_languages(context)
        minimum_confidence = float_value(
            context_option(context, "coverage_minimum_confidence", 0.0),
        )
        counts: dict[str, int] = defaultdict(int)
        characters: dict[str, int] = defaultdict(int)
        eligible_blocks = 0
        eligible_characters = 0
        for block in context.blocks:
            # Low-confidence eligible text stays in the denominator as unknown;
            # this avoids inflating target-language coverage.
            if not eligible_block(block, minimum_confidence=0.0):
                continue
            eligible_blocks += 1
            character_count = block_characters(block)
            eligible_characters += character_count
            code = block.language_code.casefold()
            if block.language_confidence < minimum_confidence:
                code = "unknown"
            counts[code] += 1
            characters[code] += character_count

        block_coverage = {
            code: percentage(counts[code], eligible_blocks)
            for code in (*languages, "unknown", "mixed", "other")
        }
        character_coverage = {
            code: percentage(characters[code], eligible_characters)
            for code in (*languages, "unknown", "mixed", "other")
        }
        mode = enum_value(
            context_option(context, "coverage_evaluation_mode", "BOTH_REQUIRED"),
        ).upper()
        generated = []
        ratios: list[float] = []
        passed: dict[str, bool] = {}
        for language in languages:
            minimum_blocks = language_threshold(
                context,
                "minimum_language_block_coverage",
                language,
                0.0,
            )
            minimum_characters = language_threshold(
                context,
                "minimum_language_character_coverage",
                language,
                0.0,
            )
            block_ratio = self._ratio(
                block_coverage[language],
                minimum_blocks,
            )
            character_ratio = self._ratio(
                character_coverage[language],
                minimum_characters,
            )
            if mode == "EITHER_REQUIRED":
                language_ratio = max(block_ratio, character_ratio)
                language_passed = block_ratio >= 1 or character_ratio >= 1
            elif mode == "CHARACTER_ONLY":
                language_ratio = character_ratio
                language_passed = character_ratio >= 1
            elif mode == "BLOCK_ONLY":
                language_ratio = block_ratio
                language_passed = block_ratio >= 1
            else:
                language_ratio = min(block_ratio, character_ratio)
                language_passed = block_ratio >= 1 and character_ratio >= 1
            ratios.append(min(1.0, language_ratio))
            passed[language] = language_passed
            if language_passed:
                continue
            severity = (
                FindingSeverity.MAJOR
                if language_ratio < 0.5
                else FindingSeverity.MINOR
            )
            generated.append(
                self.findings.create(
                    LOW_COVERAGE_CODES.get(
                        language,
                        f"LOW_{language.upper()}_COVERAGE",
                    ),
                    severity=severity,
                    language_code=language,
                    description=(
                        f"{LANGUAGE_NAMES.get(language, language)} block "
                        "or character coverage is below the configured "
                        "threshold."
                    ),
                    expected_value={
                        "blockCoverage": minimum_blocks,
                        "characterCoverage": minimum_characters,
                        "evaluationMode": mode,
                    },
                    actual_value={
                        "blockCoverage": block_coverage[language],
                        "characterCoverage": character_coverage[language],
                    },
                    metrics={"coverageRatio": round(language_ratio, 6)},
                ),
            )

        maximum_unknown = float_value(
            read(
                context.rule,
                "maximum_unknown_block_percentage",
                10.0,
            ),
            10.0,
        )
        maximum_mixed = float_value(
            read(
                context.rule,
                "maximum_mixed_block_percentage",
                20.0,
            ),
            20.0,
        )
        if block_coverage["unknown"] > maximum_unknown:
            severity = (
                FindingSeverity.MAJOR
                if block_coverage["unknown"] > maximum_unknown * 2
                else FindingSeverity.MINOR
            )
            generated.append(
                self.findings.create(
                    FindingCode.UNKNOWN_TEXT_EXCEEDS_THRESHOLD,
                    severity=severity,
                    expected_value={"maximumPercentage": maximum_unknown},
                    actual_value={
                        "blockPercentage": block_coverage["unknown"],
                    },
                ),
            )
        if block_coverage["mixed"] > maximum_mixed:
            generated.append(
                self.findings.create(
                    FindingCode.MIXED_TEXT_EXCEEDS_THRESHOLD,
                    severity=FindingSeverity.INFORMATION,
                    expected_value={"maximumPercentage": maximum_mixed},
                    actual_value={
                        "blockPercentage": block_coverage["mixed"],
                    },
                ),
            )
        evaluated = eligible_blocks > 0
        earned = (
            sum(ratios) / len(ratios) * maximum
            if evaluated and ratios
            else (maximum if evaluated else 0.0)
        )
        return result(
            self.code,
            maximum_score=maximum,
            score=earned,
            findings=generated,
            evaluated=evaluated,
            metrics={
                "evaluationMode": mode,
                "blockCoverage": block_coverage,
                "characterCoverage": character_coverage,
                "languagePassed": passed,
                "eligibleBlocks": eligible_blocks,
                "eligibleCharacters": eligible_characters,
                "unknownBlockPercentage": block_coverage["unknown"],
                "mixedBlockPercentage": block_coverage["mixed"],
            },
        )

    @staticmethod
    def _ratio(actual: float, threshold: float) -> float:
        if threshold <= 0:
            return 1.0
        return actual / threshold

