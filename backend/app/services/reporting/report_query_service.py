"""Compatibility export for the separated report query surface."""

from app.services.reporting.report_dataset_service import (
    ReportDataset,
    ReportDatasetService,
)

__all__ = ["ReportDataset", "ReportDatasetService"]
