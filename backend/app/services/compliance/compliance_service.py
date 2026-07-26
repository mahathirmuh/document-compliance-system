"""Small application-facing facade around context building and pure validation."""

from __future__ import annotations

from app.schemas.compliance_internal import ComplianceValidationContext
from app.services.compliance.compliance_context_service import (
    ComplianceContextService,
)
from app.services.compliance.compliance_pipeline import (
    CancellationCheck,
    CompliancePipeline,
)
from app.services.compliance.contracts import CompliancePipelineResult


class ComplianceService:
    """Expose stable integration points while keeping transactions outside."""

    def __init__(
        self,
        context_service: ComplianceContextService | None = None,
        pipeline: CompliancePipeline | None = None,
    ) -> None:
        self.contexts = context_service or ComplianceContextService()
        self.pipeline = pipeline or CompliancePipeline(
            context_service=self.contexts,
        )

    async def validate(
        self,
        context: ComplianceValidationContext,
        *,
        cancellation_check: CancellationCheck | None = None,
    ) -> CompliancePipelineResult:
        return await self.pipeline.run(
            context,
            cancellation_check=cancellation_check,
        )

