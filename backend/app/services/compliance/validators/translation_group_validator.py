"""Required-language completeness for confidence-qualified groups."""

from __future__ import annotations

import hashlib
import json
from typing import TypedDict
from uuid import UUID

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    TranslationGroupData,
    ValidatorResult,
)
from app.services.compliance._compat import bool_value, float_value
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    MISSING_GROUP_LANGUAGE_CODES,
    FindingCode,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.grouping.group_order_service import (
    GroupOrderService,
)
from app.services.compliance.validators._helpers import (
    context_option,
    required_languages,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class _GroupFindingArguments(TypedDict):
    severity: str
    confidence: float
    source_reference: str
    container_id: UUID | None
    detected_section_code: str | None
    translation_group_signature: str
    expected_value: dict[str, object]
    actual_value: dict[str, object]
    metrics: dict[str, object]


class TranslationGroupValidator(BaseComplianceValidator):
    code = "TRANSLATION_GROUPS"
    name = "Translation group completeness"
    weight = 15.0

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
        expected = required_languages(context)
        minimum_confidence = float_value(
            context_option(context, "translation_group_min_confidence", 0.65),
            0.65,
        )
        evaluated = 0
        complete = 0
        low_confidence = 0
        generated = []
        for group in context.translation_groups:
            missing = self.order.missing_languages(
                group.detected_languages,
                expected,
            )
            signature = group_signature(group)
            if group.confidence < minimum_confidence:
                low_confidence += 1
                if missing:
                    generated.append(
                        self.findings.create(
                            FindingCode.INCOMPLETE_TRANSLATION_GROUP,
                            severity=FindingSeverity.INFORMATION,
                            confidence=group.confidence,
                            source_reference=group.source_reference,
                            container_id=group.container_id,
                            detected_section_code=(
                                group.detected_section_code
                            ),
                            translation_group_signature=signature,
                            expected_value={
                                "requiredLanguages": list(expected),
                            },
                            actual_value={
                                "detectedLanguages": (
                                    group.detected_languages
                                ),
                                "missingLanguages": list(missing),
                            },
                            metrics={
                                "groupIndex": group.group_index,
                                "lowConfidence": True,
                            },
                        ),
                    )
                continue
            evaluated += 1
            if not missing:
                complete += 1
                continue
            in_required_section = bool_value(
                group.metrics.get("requiredSection", False),
            )
            severity = (
                FindingSeverity.MAJOR
                if in_required_section or len(missing) > 1
                else FindingSeverity.MINOR
            )
            common: _GroupFindingArguments = {
                "severity": severity,
                "confidence": group.confidence,
                "source_reference": group.source_reference,
                "container_id": group.container_id,
                "detected_section_code": group.detected_section_code,
                "translation_group_signature": signature,
                "expected_value": {
                    "requiredLanguages": list(expected),
                },
                "actual_value": {
                    "detectedLanguages": group.detected_languages,
                    "missingLanguages": list(missing),
                },
                "metrics": {"groupIndex": group.group_index},
            }
            generated.append(
                self.findings.create(
                    FindingCode.INCOMPLETE_TRANSLATION_GROUP,
                    **common,
                ),
            )
            for language in missing:
                generated.append(
                    self.findings.create(
                        MISSING_GROUP_LANGUAGE_CODES.get(
                            language,
                            f"MISSING_TRANSLATION_GROUP_{language.upper()}",
                        ),
                        description=(
                            "Structural group lacks "
                            f"{LANGUAGE_NAMES.get(language, language)}."
                        ),
                        language_code=language,
                        **common,
                    ),
                )
        earned = complete / evaluated * maximum if evaluated else 0.0
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
                        "excluded from completeness scoring."
                    )
                ]
                if low_confidence
                else []
            ),
            metrics={
                "totalGroups": len(context.translation_groups),
                "evaluatedGroups": evaluated,
                "completeGroups": complete,
                "incompleteGroups": evaluated - complete,
                "lowConfidenceGroups": low_confidence,
            },
        )


def group_signature(group: TranslationGroupData) -> str:
    payload = {
        "containerId": str(group.container_id or ""),
        "groupType": group.group_type,
        "sourceReference": group.source_reference,
        "memberReferences": [
            member.source_reference for member in group.members
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
