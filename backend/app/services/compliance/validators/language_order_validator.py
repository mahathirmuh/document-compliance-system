"""Expected language sequence validation inside structural groups."""

from __future__ import annotations

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import bool_value, enum_value, float_value
from app.services.compliance.constants import FindingCode, FindingSeverity
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.grouping.group_order_service import (
    GroupOrderService,
)
from app.services.compliance.validators._helpers import (
    context_option,
    expected_language_order,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class LanguageOrderValidator(BaseComplianceValidator):
    code = "LANGUAGE_ORDER"
    name = "Language order"
    weight = 10.0

    def __init__(
        self,
        finding_factory: FindingFactory | None = None,
        order_service: GroupOrderService | None = None,
    ) -> None:
        self.findings = finding_factory or FindingFactory()
        self.order = order_service or GroupOrderService()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        expected = expected_language_order(context)
        minimum_confidence = float_value(
            context_option(context, "translation_group_min_confidence", 0.65),
            0.65,
        )
        allow_missing = bool_value(
            context_option(
                context,
                "allow_missing_language_before_order_check",
                False,
            ),
        )
        mixed_handling = enum_value(
            context_option(context, "mixed_block_handling", "IGNORE"),
        ).upper()
        ignore_mixed = mixed_handling == "IGNORE"
        evaluated = 0
        valid_count = 0
        low_confidence = 0
        generated = []
        details: list[dict[str, object]] = []
        for group in context.translation_groups:
            actual = tuple(group.language_order)
            valid = self.order.is_valid(
                actual,
                expected,
                allow_missing=allow_missing,
                ignore_unknown=bool_value(
                    context_option(context, "ignore_unknown_blocks", True),
                    True,
                ),
                ignore_mixed=ignore_mixed,
            )
            if group.confidence < minimum_confidence:
                low_confidence += 1
                if not valid:
                    generated.append(
                        self.findings.create(
                            FindingCode.LANGUAGE_ORDER_INVALID,
                            severity=FindingSeverity.INFORMATION,
                            confidence=group.confidence,
                            source_reference=group.source_reference,
                            container_id=group.container_id,
                            detected_section_code=(
                                group.detected_section_code
                            ),
                            expected_value={"order": list(expected)},
                            actual_value={"order": list(actual)},
                            metrics={
                                "groupIndex": group.group_index,
                                "lowConfidence": True,
                            },
                        ),
                    )
                continue
            evaluated += 1
            if valid:
                valid_count += 1
            else:
                generated.append(
                    self.findings.create(
                        FindingCode.LANGUAGE_ORDER_INVALID,
                        severity=FindingSeverity.MINOR,
                        confidence=group.confidence,
                        source_reference=group.source_reference,
                        container_id=group.container_id,
                        detected_section_code=group.detected_section_code,
                        expected_value={"order": list(expected)},
                        actual_value={"order": list(actual)},
                        metrics={"groupIndex": group.group_index},
                    ),
                )
            details.append(
                {
                    "groupIndex": group.group_index,
                    "expected": list(expected),
                    "actual": list(actual),
                    "valid": valid,
                    "confidence": group.confidence,
                },
            )
        earned = (
            valid_count / evaluated * maximum if evaluated else 0.0
        )
        status = None
        if not evaluated:
            status = "NEEDS_REVIEW" if low_confidence else "NOT_EVALUATED"
        return result(
            self.code,
            maximum_score=maximum,
            score=earned,
            findings=generated,
            status=status,
            evaluated=bool(evaluated),
            warnings=(
                [
                    (
                        f"{low_confidence} low-confidence groups were "
                        "excluded from the language-order denominator."
                    )
                ]
                if low_confidence
                else []
            ),
            metrics={
                "expectedOrder": list(expected),
                "evaluatedGroups": evaluated,
                "validGroups": valid_count,
                "invalidGroups": evaluated - valid_count,
                "lowConfidenceGroups": low_confidence,
                "groups": details,
            },
        )
