"""Configured canonical-section order validation."""

from __future__ import annotations

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import bool_value, first, string_list
from app.services.compliance.constants import (
    DEFAULT_SECTION_ORDER,
    FindingCode,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.validators._helpers import (
    result,
    skipped_result,
    validator_enabled,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class SectionOrderValidator(BaseComplianceValidator):
    code = "SECTION_ORDER"
    name = "Section order"
    weight = 0.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code, scoring=False)
        options = context.rule.validation_options
        if not bool_value(
            first(
                options,
                "validate_section_order",
                "validateSectionOrder",
                default=True,
            ),
            True,
        ):
            return result(
                self.code,
                maximum_score=0,
                score=0,
                status="SKIPPED",
                metrics={"enabled": False},
            )
        configured = string_list(
            first(
                options,
                "expected_section_order",
                "expectedSectionOrder",
                default=DEFAULT_SECTION_ORDER,
            ),
        )
        expected = tuple(section.upper() for section in configured)
        actual = tuple(
            section.canonical_code.upper()
            for section in sorted(
                context.detected_sections,
                key=lambda item: item.section_order,
            )
            if section.canonical_code.upper() in expected
        )
        allow_repeated = bool_value(
            first(
                options,
                "allow_repeated_sections",
                "allowRepeatedSections",
                default=False,
            ),
        )
        positions = {code: index for index, code in enumerate(expected)}
        numeric = [positions[code] for code in actual]
        duplicate_invalid = (
            not allow_repeated and len(actual) != len(set(actual))
        )
        valid = numeric == sorted(numeric) and not duplicate_invalid
        generated = []
        if not valid:
            generated.append(
                self.findings.create(
                    FindingCode.SECTION_ORDER_INVALID,
                    severity=FindingSeverity.MINOR,
                    expected_value={"order": list(expected)},
                    actual_value={"order": list(actual)},
                ),
            )
        return result(
            self.code,
            maximum_score=0,
            score=0,
            findings=generated,
            status="PASSED" if valid else "FAILED",
            metrics={
                "expected": list(expected),
                "actual": list(actual),
                "valid": valid,
                "allowRepeatedSections": allow_repeated,
            },
        )

