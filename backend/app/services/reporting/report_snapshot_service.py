"""Compatibility export for report snapshot lifecycle operations."""

from app.services.reporting.advanced_reporting_service import (
    AdvancedReportingService,
    ReportDownload,
)

ReportSnapshotService = AdvancedReportingService

__all__ = [
    "AdvancedReportingService",
    "ReportDownload",
    "ReportSnapshotService",
]
