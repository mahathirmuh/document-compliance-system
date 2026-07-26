"""Cell-level missing-language findings for structurally detected tables."""

from __future__ import annotations

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import first, mapping, read
from app.services.compliance.constants import (
    FindingCode,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.grouping.group_order_service import (
    GroupOrderService,
)
from app.services.compliance.grouping.table_grouping_service import (
    TableGroupingService,
)
from app.services.compliance.validators._helpers import (
    required_languages,
    result,
    skipped_result,
    validator_enabled,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class CellMultilingualValidator(BaseComplianceValidator):
    code = "CELL_MULTILINGUAL"
    name = "Cell multilingual completeness"
    weight = 0.0

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
            return skipped_result(context, self.code, scoring=False)
        expected = required_languages(context)
        groups = self.grouping.group_tables(context.tables, expected)
        generated = []
        for group in groups:
            missing = self.order.missing_languages(
                group.detected_languages,
                expected,
            )
            if not missing:
                continue
            metrics = mapping(group.metrics)
            missing_cells = mapping(read(metrics, "missingCells", {}))
            for language in missing:
                coordinate = first(
                    missing_cells,
                    language,
                    default=first(
                        metrics,
                        "coordinate",
                        default=None,
                    ),
                )
                generated.append(
                    self.findings.create(
                        FindingCode.TABLE_CELL_LANGUAGE_MISSING,
                        severity=FindingSeverity.MINOR,
                        confidence=group.confidence,
                        language_code=language,
                        container_id=group.container_id,
                        source_reference=group.source_reference,
                        cell_coordinate=coordinate,
                        expected_value={"requiredLanguage": language},
                        actual_value={"present": False},
                        metrics={"groupIndex": group.group_index},
                    ),
                )
        return result(
            self.code,
            maximum_score=0,
            score=0,
            findings=generated,
            status="PASSED" if not generated else "FAILED",
            metrics={
                "evaluatedGroups": len(groups),
                "missingCellLanguages": len(generated),
            },
        )
