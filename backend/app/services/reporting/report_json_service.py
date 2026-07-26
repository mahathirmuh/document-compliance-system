"""UTF-8 JSON advanced report serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.schemas.advanced_reporting import AdvancedReportFilters
from app.services.reporting.report_dataset_service import ReportDataset


class ReportJsonService:
    @staticmethod
    def build(
        dataset: ReportDataset,
        *,
        report_name: str,
        filters: AdvancedReportFilters,
    ) -> bytes:
        payload = {
            "metadata": {
                "reportName": report_name,
                "reportType": dataset.report_type.value,
                "generatedAt": datetime.now(UTC).isoformat(),
                "disclaimer": (
                    "Automated quality metrics are review signals and do not "
                    "constitute legal or linguistic proof."
                ),
            },
            "filters": filters.model_dump(mode="json", by_alias=True),
            "summary": dataset.summary,
            "dataSeries": dataset.data_series,
            "tableData": dataset.tables,
            "warnings": dataset.warnings,
        }
        return json.dumps(
            payload, ensure_ascii=False, indent=2, default=str
        ).encode("utf-8")
