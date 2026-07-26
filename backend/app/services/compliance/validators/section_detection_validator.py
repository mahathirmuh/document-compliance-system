"""Validate confidence and availability of pre-detected canonical sections."""

from __future__ import annotations

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import float_value
from app.services.compliance.constants import ValidatorStatus
from app.services.compliance.validators._helpers import (
    context_option,
    result,
    skipped_result,
    validator_enabled,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class SectionDetectionValidator(BaseComplianceValidator):
    code = "SECTION_DETECTION"
    name = "Section detection"
    weight = 0.0

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code, scoring=False)
        threshold = float_value(
            context_option(context, "section_match_min_confidence", 0.80),
            0.80,
        )
        low_confidence = [
            section
            for section in context.detected_sections
            if section.match_confidence < threshold
        ]
        warnings = [
            (
                f"Section {section.canonical_code} matched below the "
                "configured confidence threshold."
            )
            for section in low_confidence
        ]
        if not context.detected_sections:
            status = ValidatorStatus.NEEDS_REVIEW
            warnings.append("No canonical section heading was detected.")
        elif low_confidence:
            status = ValidatorStatus.NEEDS_REVIEW
        else:
            status = ValidatorStatus.PASSED
        return result(
            self.code,
            maximum_score=0,
            score=0,
            status=status,
            warnings=warnings,
            metrics={
                "detectedSectionCount": len(context.detected_sections),
                "lowConfidenceSectionCount": len(low_confidence),
                "minimumConfidence": threshold,
            },
        )

