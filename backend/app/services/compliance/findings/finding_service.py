"""Facade for pure finding generation and revalidation handling."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.compliance_internal import FindingDraft
from app.services.compliance.findings.finding_deduplication_service import (
    FindingDeduplicationService,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.findings.finding_resolution_service import (
    FindingResolutionService,
)
from app.services.compliance.findings.finding_summary_service import (
    FindingSummaryService,
)


class FindingService:
    def __init__(self) -> None:
        self.factory = FindingFactory()
        self.deduplication = FindingDeduplicationService()
        self.resolution = FindingResolutionService()
        self.summary = FindingSummaryService()

    def create_manual(self, **values: object) -> FindingDraft:
        return self.factory.manual(
            severity=str(values.pop("severity")),
            title=str(values.pop("title")),
            description=str(values.pop("description")),
            recommendation=str(values.pop("recommendation", "")),
            **values,
        )

    def prepare_run_findings(
        self,
        findings: Sequence[object],
        *,
        previous_findings: Sequence[object] = (),
    ) -> list[object]:
        if previous_findings:
            return self.deduplication.merge_revalidation(
                findings,
                previous_findings,
            )
        return self.deduplication.deduplicate(findings)
