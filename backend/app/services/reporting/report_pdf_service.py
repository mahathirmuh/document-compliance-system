"""Privacy-bounded ReportLab advanced report output."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from html import escape

from app.schemas.advanced_reporting import AdvancedReportFilters
from app.services.reporting.report_dataset_service import ReportDataset


class ReportPdfService:
    def __init__(
        self, *, maximum_rows: int, maximum_text_characters: int = 500
    ) -> None:
        self.maximum_rows = maximum_rows
        self.maximum_text_characters = maximum_text_characters

    def build(
        self,
        dataset: ReportDataset,
        *,
        report_name: str,
        filters: AdvancedReportFilters,
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
        )

        output = io.BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title=report_name,
        )
        styles = getSampleStyleSheet()
        story: list[object] = [
            Paragraph(escape(report_name), styles["Title"]),
            Spacer(1, 8),
            Paragraph(
                f"Report type: {dataset.report_type.value}",
                styles["Normal"],
            ),
            Paragraph(
                f"Generated: {datetime.now(UTC).isoformat()}",
                styles["Normal"],
            ),
            Paragraph(
                "Filters: "
                + escape(
                    str(filters.model_dump(mode="json", by_alias=True))
                ),
                styles["BodyText"],
            ),
            Spacer(1, 10),
            Paragraph("Executive metrics", styles["Heading2"]),
        ]
        metric_rows = [["Metric", "Value"]] + [
            [escape(str(key)), escape(str(value))]
            for key, value in dataset.summary.items()
        ]
        metrics = Table(metric_rows, repeatRows=1)
        metrics.setStyle(self._table_style(colors))
        story.extend([metrics, PageBreak()])

        remaining = self.maximum_rows
        for name, rows in dataset.tables.items():
            story.append(Paragraph(escape(name), styles["Heading2"]))
            bounded = rows[:remaining]
            if not bounded:
                story.append(Paragraph("No data.", styles["BodyText"]))
                continue
            headers = list(bounded[0].keys())
            table_rows = [[escape(str(header)) for header in headers]]
            table_rows.extend(
                [
                    [
                        Paragraph(
                            escape(self._bounded_text(row.get(header))),
                            styles["BodyText"],
                        )
                        for header in headers
                    ]
                    for row in bounded
                ]
            )
            table = Table(table_rows, repeatRows=1)
            table.setStyle(self._table_style(colors))
            story.extend([table, Spacer(1, 8)])
            remaining -= len(bounded)
            if remaining <= 0:
                story.append(
                    Paragraph(
                        "Detailed rows were truncated at the configured PDF "
                        "limit.",
                        styles["Italic"],
                    )
                )
                break
        if dataset.warnings:
            story.append(Paragraph("Warnings", styles["Heading2"]))
            for warning in dataset.warnings:
                story.append(Paragraph(escape(warning), styles["BodyText"]))
        story.extend(
            [
                Spacer(1, 10),
                Paragraph("Disclaimer", styles["Heading2"]),
                Paragraph(
                    (
                        "Automated quality metrics are review signals and do "
                        "not constitute legal or linguistic proof. Full "
                        "document text, OCR images, storage paths, tokens, "
                        "and internal exception details are excluded."
                    ),
                    styles["BodyText"],
                ),
            ]
        )
        document.build(story)
        return output.getvalue()

    @staticmethod
    def _table_style(colors):
        from reportlab.platypus import TableStyle

        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    def _bounded_text(self, value: object) -> str:
        text = str(value if value is not None else "")
        return text[: self.maximum_text_characters]
