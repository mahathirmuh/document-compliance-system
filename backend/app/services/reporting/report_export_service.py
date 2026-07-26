"""Select stable advanced report serializers by requested format."""

from __future__ import annotations

from app.models.report_snapshot import ReportFileFormat
from app.schemas.advanced_reporting import AdvancedReportFilters
from app.services.reporting.report_dataset_service import ReportDataset
from app.services.reporting.report_json_service import ReportJsonService
from app.services.reporting.report_pdf_service import ReportPdfService
from app.services.reporting.report_xlsx_service import ReportXlsxService


class ReportExportService:
    def __init__(
        self,
        *,
        xlsx_maximum_rows: int,
        pdf_maximum_rows: int,
        text_maximum_characters: int = 500,
    ) -> None:
        self.xlsx = ReportXlsxService(maximum_rows=xlsx_maximum_rows)
        self.pdf = ReportPdfService(
            maximum_rows=pdf_maximum_rows,
            maximum_text_characters=text_maximum_characters,
        )

    def build(
        self,
        dataset: ReportDataset,
        *,
        report_name: str,
        filters: AdvancedReportFilters,
        output_format: ReportFileFormat,
    ) -> bytes:
        if output_format is ReportFileFormat.JSON:
            return ReportJsonService.build(
                dataset, report_name=report_name, filters=filters
            )
        if output_format is ReportFileFormat.XLSX:
            return self.xlsx.build(
                dataset, report_name=report_name, filters=filters
            )
        return self.pdf.build(
            dataset, report_name=report_name, filters=filters
        )

    @staticmethod
    def media_type(output_format: ReportFileFormat) -> str:
        return {
            ReportFileFormat.JSON: "application/json",
            ReportFileFormat.XLSX: (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            ReportFileFormat.PDF: "application/pdf",
        }[output_format]
