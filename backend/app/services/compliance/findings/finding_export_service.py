"""Bounded private JSON/XLSX exports for department-scoped findings."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.authorization import AuditAction, Permission
from app.core.config import Settings
from app.models.document import Document
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.schemas.finding import FindingFilter
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_export_service import (
    ComplianceExportService,
    safe_source_reference,
    spreadsheet_safe_value,
)
from app.services.compliance.findings.finding_management_service import (
    FindingManagementService,
)
from app.services.documents.base import document_error

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_WORKBOOK_COLUMNS = (
    "Document Code",
    "Revision",
    "Department",
    "Finding Code",
    "Finding Type",
    "Severity",
    "Status",
    "Title",
    "Description",
    "Recommendation",
    "Language",
    "Section",
    "Page",
    "Worksheet",
    "Cell",
    "Source Reference",
    "Assigned To",
    "Created At",
    "Reviewed At",
    "Resolved At",
)


@dataclass(frozen=True, slots=True)
class FindingExportArtifact:
    path: Path
    filename: str
    media_type: str


class FindingExportService(FindingManagementService):
    """Export only retained finding metadata, never source-file content."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.export_builder = ComplianceExportService(
            maximum_rows=settings.finding_export_max_rows
        )

    async def export(
        self,
        filters: FindingFilter,
        *,
        export_format: str,
    ) -> FindingExportArtifact:
        self._ensure_permission(Permission.FINDINGS_EXPORT)
        self._validate_filter_window(filters)
        normalized = export_format.strip().lower()
        if normalized not in {"json", "xlsx"}:
            raise document_error(
                "Export format must be either json or xlsx.",
                field="format",
                code="FINDING_EXPORT_FORMAT_INVALID",
                title="Finding export format is invalid.",
            )
        department_ids = self._scope_department_ids(filters.department_id)
        predicates = self._filter_predicates(
            filters,
            department_ids=department_ids,
        )
        total = int(
            (
                await self.session.scalar(
                    select(func.count(ValidationFinding.id))
                    .join(
                        Document,
                        Document.id == ValidationFinding.document_id,
                    )
                    .where(*predicates)
                )
            )
            or 0
        )
        if total > self.settings.finding_export_max_rows:
            raise document_error(
                "The filtered findings exceed the configured export limit.",
                code="FINDING_EXPORT_LIMIT_EXCEEDED",
                status_code=413,
                title="Finding export is too large.",
            )
        statement = (
            select(ValidationFinding)
            .join(
                Document,
                Document.id == ValidationFinding.document_id,
            )
            .options(*self._export_options())
            .where(*predicates)
        )
        statement = self._apply_sort(
            statement,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        ).limit(self.settings.finding_export_max_rows + 1)
        findings = list((await self.session.scalars(statement)).unique().all())
        if len(findings) > self.settings.finding_export_max_rows:
            raise document_error(
                "The filtered findings exceed the configured export limit.",
                code="FINDING_EXPORT_LIMIT_EXCEEDED",
                status_code=413,
                title="Finding export is too large.",
            )
        records = [_finding_export_record(item) for item in findings]

        descriptor, raw_path = tempfile.mkstemp(
            prefix="compliance-findings-",
            suffix=f".{normalized}",
        )
        os.close(descriptor)
        path = Path(raw_path)
        try:
            if normalized == "json":
                payload = {
                    "items": records,
                    "totalItems": len(records),
                    "filters": filters.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude={"page", "page_size"},
                    ),
                    "limitations": {
                        "structuralValidationOnly": True,
                        "semanticSimilarityEvaluated": False,
                    },
                }
                await asyncio.to_thread(_write_json, path, payload)
                media_type = "application/json"
            else:
                rows = self.export_builder.finding_rows(
                    [_finding_workbook_row(item) for item in findings]
                )
                await asyncio.to_thread(_write_workbook, path, rows)
                media_type = _XLSX_MEDIA_TYPE
            await self.audit(
                action=AuditAction.EXPORT_FINDINGS,
                entity_type="ValidationFinding",
                entity_id=None,
                description="Filtered compliance findings exported.",
                new_values={
                    "format": normalized,
                    "rowCount": len(records),
                    "departmentId": (
                        str(filters.department_id)
                        if filters.department_id is not None
                        else None
                    ),
                    "structuralValidationOnly": True,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            remove_finding_export_artifact(path)
            raise
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return FindingExportArtifact(
            path=path,
            filename=f"compliance_findings_{timestamp}.{normalized}",
            media_type=media_type,
        )

    @staticmethod
    def _export_options() -> tuple[object, ...]:
        return (
            selectinload(ValidationFinding.document).selectinload(Document.department),
            selectinload(ValidationFinding.revision),
            selectinload(ValidationFinding.detected_section),
            selectinload(ValidationFinding.assignee),
        )


def _finding_export_record(
    finding: ValidationFinding,
) -> dict[str, object]:
    document = finding.document
    revision = finding.revision
    department = document.department
    section = finding.detected_section
    assignee = finding.assignee
    return {
        "id": str(finding.id),
        "documentId": str(finding.document_id),
        "documentRevisionId": str(finding.document_revision_id),
        "documentFileId": str(finding.document_file_id),
        "complianceRunId": (
            str(finding.compliance_run_id)
            if finding.compliance_run_id is not None
            else None
        ),
        "documentCode": document.base_document_code,
        "revision": revision.revision_code,
        "department": department.name,
        "findingCode": finding.finding_code.value,
        "findingType": finding.finding_type.value,
        "severity": finding.severity.value,
        "status": finding.status.value,
        "title": finding.title,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "language": finding.language_code,
        "section": section.canonical_code if section is not None else None,
        "page": finding.page_number,
        "worksheet": finding.worksheet_name,
        "cell": finding.cell_coordinate,
        "sourceReference": (
            safe_source_reference(finding.source_reference)
            if finding.source_reference is not None
            else None
        ),
        "assignedTo": assignee.name if assignee is not None else None,
        "isSystemGenerated": finding.is_system_generated,
        "isRepeat": finding.is_repeat,
        "createdAt": finding.created_at.isoformat(),
        "reviewedAt": (
            finding.reviewed_at.isoformat() if finding.reviewed_at is not None else None
        ),
        "resolvedAt": (
            finding.resolved_at.isoformat() if finding.resolved_at is not None else None
        ),
    }


def _finding_workbook_row(
    finding: ValidationFinding,
) -> dict[str, object]:
    record = _finding_export_record(finding)
    return {
        "Document Code": record["documentCode"],
        "Revision": record["revision"],
        "Department": record["department"],
        "Finding Code": record["findingCode"],
        "Finding Type": record["findingType"],
        "Severity": record["severity"],
        "Status": record["status"],
        "Title": record["title"],
        "Description": record["description"],
        "Recommendation": record["recommendation"],
        "Language": record["language"],
        "Section": record["section"],
        "Page": record["page"],
        "Worksheet": record["worksheet"],
        "Cell": record["cell"],
        "Source Reference": record["sourceReference"],
        "Assigned To": record["assignedTo"],
        "Created At": record["createdAt"],
        "Reviewed At": record["reviewedAt"],
        "Resolved At": record["resolvedAt"],
    }


def _write_workbook(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Findings")
    sheet.append([spreadsheet_safe_value(column) for column in _WORKBOOK_COLUMNS])
    for row in rows:
        sheet.append([row.get(column) for column in _WORKBOOK_COLUMNS])
    workbook.save(path)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(
            payload,
            output,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def remove_finding_export_artifact(path: Path) -> None:
    """Delete only the exact private temporary artifact for one response."""

    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
    except OSError:
        return
