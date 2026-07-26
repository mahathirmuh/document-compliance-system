"""Multilingual table row/column completeness and header order."""

from __future__ import annotations

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance.constants import (
    FindingCode,
    FindingSeverity,
    ValidatorStatus,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.grouping.group_order_service import (
    GroupOrderService,
)
from app.services.compliance.grouping.table_grouping_service import (
    TableGroupingService,
)
from app.services.compliance.validators._helpers import (
    expected_language_order,
    required_languages,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)
from app.services.compliance.validators.translation_group_validator import (
    group_signature,
)

_TABLE_GROUP_TYPES = {
    "TABLE_ROW_GROUP",
    "TABLE_CELL_GROUP",
    "XLSX_ROW_GROUP",
}


class TableMultilingualValidator(BaseComplianceValidator):
    code = "TABLE_MULTILINGUAL"
    name = "Table multilingual completeness"
    weight = 5.0

    def __init__(
        self,
        finding_factory: FindingFactory | None = None,
        grouping_service: TableGroupingService | None = None,
    ) -> None:
        self.findings = finding_factory or FindingFactory()
        self.grouping = grouping_service or TableGroupingService()
        self.order = GroupOrderService()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        expected = required_languages(context)
        groups = [
            group
            for group in context.translation_groups
            if group.group_type.upper() in _TABLE_GROUP_TYPES
        ]
        if not groups and not context.tables:
            return result(
                self.code,
                maximum_score=maximum,
                score=maximum,
                status=ValidatorStatus.SKIPPED,
                metrics={
                    "enabled": True,
                    "applicable": False,
                    "evaluatedTableGroups": 0,
                    "completeTableGroups": 0,
                    "incompleteTableGroups": 0,
                    "invalidHeaderOrders": 0,
                    "layouts": [],
                },
            )
        if not groups and context.tables:
            groups = self.grouping.group_tables(context.tables, expected)
        complete = sum(group.is_complete for group in groups)
        generated = []
        for group in groups:
            if group.is_complete:
                continue
            missing = self.order.missing_languages(
                group.detected_languages,
                expected,
            )
            code = (
                FindingCode.XLSX_ROW_TRANSLATION_INCOMPLETE
                if group.group_type.upper() == "XLSX_ROW_GROUP"
                else FindingCode.TABLE_TRANSLATION_INCOMPLETE
            )
            generated.append(
                self.findings.create(
                    code,
                    severity=FindingSeverity.MAJOR,
                    confidence=group.confidence,
                    container_id=group.container_id,
                    source_reference=group.source_reference,
                    detected_section_code=group.detected_section_code,
                    translation_group_signature=group_signature(group),
                    expected_value={
                        "requiredLanguages": list(expected),
                    },
                    actual_value={
                        "detectedLanguages": group.detected_languages,
                        "missingLanguages": list(missing),
                    },
                    metrics={"groupIndex": group.group_index},
                ),
            )
        layouts = [
            self.grouping.detect_layout(table, expected)
            for table in context.tables
        ]
        expected_order = expected_language_order(context)
        invalid_headers = [
            layout
            for layout in layouts
            if layout.header_order
            and not self.order.is_valid(
                layout.header_order,
                expected_order,
                allow_missing=False,
            )
        ]
        for layout in invalid_headers:
            generated.append(
                self.findings.create(
                    FindingCode.LANGUAGE_ORDER_INVALID,
                    severity=FindingSeverity.MINOR,
                    expected_value={"order": list(expected_order)},
                    actual_value={"order": list(layout.header_order)},
                    metrics={"tableHeader": True, "layout": layout.layout},
                ),
            )
        earned = complete / len(groups) * maximum if groups else 0.0
        return result(
            self.code,
            maximum_score=maximum,
            score=earned,
            findings=generated,
            evaluated=bool(groups),
            metrics={
                "evaluatedTableGroups": len(groups),
                "completeTableGroups": complete,
                "incompleteTableGroups": len(groups) - complete,
                "invalidHeaderOrders": len(invalid_headers),
                "layouts": [
                    {
                        "layout": layout.layout,
                        "confidence": layout.confidence,
                        "headerOrder": list(layout.header_order),
                    }
                    for layout in layouts
                ],
            },
        )
