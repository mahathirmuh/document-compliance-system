"""Private bounded JSON/XLSX export of retained compliance evidence."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_export_service import (
    ComplianceExportService,
    spreadsheet_safe_value,
)
from app.services.compliance.compliance_query_service import (
    ComplianceQueryService,
    compliance_run_response,
    detected_section_response,
    translation_group_response,
)
from app.services.documents.base import document_error

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class ComplianceExportArtifact:
    path: Path
    filename: str
    media_type: str


class ComplianceResultExportService(ComplianceQueryService):
    """Serialize only scoped stored results; no source binaries are read."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, settings, user, metadata)
        self.export_builder = ComplianceExportService(
            maximum_rows=settings.compliance_export_max_rows
        )

    async def export(
        self,
        run_id: UUID,
        *,
        export_format: str,
    ) -> ComplianceExportArtifact:
        if not has_permission(
            self.user.role,
            Permission.COMPLIANCE_EXPORT,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()
        normalized = export_format.strip().lower()
        if normalized not in {"json", "xlsx"}:
            raise document_error(
                "Export format must be either json or xlsx.",
                field="format",
                code="COMPLIANCE_EXPORT_FORMAT_INVALID",
                title="Compliance export format is invalid.",
            )
        run = await self._run(run_id)
        section_repository = self._detected_section_repository()
        section_total = await section_repository.count_for_run(run.id)
        section_language_total = (
            await section_repository.count_language_results_for_run(run.id)
        )
        group_total = await self.groups.count_for_run(run.id)
        group_member_total = await self.groups.count_members_for_run(run.id)
        finding_total = await self.findings.count_for_run(run.id)
        maximum = self.settings.compliance_export_max_rows
        if (
            max(
                section_total,
                section_language_total,
                group_total,
                group_member_total,
                finding_total,
            )
            > maximum
            or group_total
            > self.settings.compliance_max_translation_groups
            or group_member_total > self.settings.compliance_max_blocks
        ):
            raise document_error(
                "The compliance result exceeds the configured export limit.",
                code="COMPLIANCE_EXPORT_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance result is too large to export.",
            )
        sections = await self._all_sections(run.id, total=section_total)
        groups = await self._all_groups(run.id, total=group_total)
        findings = await self._all_findings(run.id, total=finding_total)
        run_response = compliance_run_response(run)
        score = await self.score_breakdown(run.id)
        summary = await self.summary(run.id)
        descriptor, raw_path = tempfile.mkstemp(
            prefix="compliance-result-",
            suffix=f".{normalized}",
        )
        os.close(descriptor)
        path = Path(raw_path)
        try:
            if normalized == "json":
                payload = self.export_builder.json_payload(
                    run_response,
                    score_breakdown=score,
                    languages=summary.language,
                    sections=sections,
                    translation_groups=groups,
                    findings=findings,
                )
                await asyncio.to_thread(_write_json, path, payload)
                media_type = "application/json"
            else:
                sheets = self.export_builder.workbook_data(
                    run_response,
                    score_breakdown=score,
                    languages=summary.language,
                    sections=sections,
                    translation_groups=groups,
                    findings=findings,
                )
                await asyncio.to_thread(_write_workbook, path, sheets)
                media_type = (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            await self.audit(
                action=AuditAction.EXPORT_COMPLIANCE_RESULT,
                entity_type="ComplianceRun",
                entity_id=run.id,
                description="Compliance result exported.",
                new_values={
                    "format": normalized,
                    "documentFileId": str(run.document_file_id),
                    "rowCounts": {
                        "sections": len(sections),
                        "translationGroups": len(groups),
                        "findings": len(findings),
                    },
                    "structuralValidationOnly": True,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            remove_compliance_export_artifact(path)
            raise
        code = _SAFE_FILENAME_RE.sub(
            "-",
            run.revision.full_document_code,
        ).strip("-")[:120]
        return ComplianceExportArtifact(
            path=path,
            filename=f"{code or 'document'}_compliance.{normalized}",
            media_type=media_type,
        )

    async def _all_sections(
        self,
        run_id: UUID,
        *,
        total: int,
    ) -> list[object]:
        if total == 0:
            return []
        output: list[object] = []
        page = 1
        page_size = min(self.settings.compliance_db_batch_size, total)
        section_repository = self._detected_section_repository()
        while len(output) < total:
            items = await section_repository.list_for_run(
                run_id,
                page=page,
                page_size=page_size,
            )
            output.extend(
                detected_section_response(item) for item in items
            )
            if not items:
                break
            page += 1
        return output

    async def _all_groups(
        self,
        run_id: UUID,
        *,
        total: int,
    ) -> list[object]:
        if total == 0:
            return []
        output: list[object] = []
        page = 1
        page_size = min(self.settings.compliance_db_batch_size, total)
        while len(output) < total:
            items, _ = await self.groups.list_for_run(
                run_id,
                page=page,
                page_size=page_size,
            )
            output.extend(
                translation_group_response(item) for item in items
            )
            if not items:
                break
            page += 1
        return output

    async def _all_findings(
        self,
        run_id: UUID,
        *,
        total: int,
    ) -> list[dict[str, object]]:
        if total == 0:
            return []
        output: list[dict[str, object]] = []
        page = 1
        page_size = min(self.settings.compliance_db_batch_size, total)
        while len(output) < total:
            items = await self.findings.list_for_run(
                run_id,
                page=page,
                page_size=page_size,
            )
            output.extend(_finding_export_row(item) for item in items)
            if not items:
                break
            page += 1
        return output


def _finding_export_row(finding: ValidationFinding) -> dict[str, object]:
    return {
        "id": str(finding.id),
        "findingCode": finding.finding_code.value,
        "findingType": finding.finding_type.value,
        "severity": finding.severity.value,
        "status": finding.status.value,
        "title": finding.title,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "languageCode": finding.language_code,
        "pageNumber": finding.page_number,
        "worksheetName": finding.worksheet_name,
        "cellCoordinate": finding.cell_coordinate,
        "sourceReference": finding.source_reference,
        "assignedTo": (
            str(finding.assigned_to)
            if finding.assigned_to is not None
            else None
        ),
        "isSystemGenerated": finding.is_system_generated,
        "isRepeat": finding.is_repeat,
        "createdAt": finding.created_at.isoformat(),
        "reviewedAt": (
            finding.reviewed_at.isoformat()
            if finding.reviewed_at is not None
            else None
        ),
        "resolvedAt": (
            finding.resolved_at.isoformat()
            if finding.resolved_at is not None
            else None
        ),
    }


def _write_workbook(
    path: Path,
    sheets: dict[str, list[dict[str, object]]],
) -> None:
    workbook = Workbook(write_only=True)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name[:31])
        if not rows:
            sheet.append(["No data"])
            continue
        headers: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    headers.append(key)
        sheet.append([spreadsheet_safe_value(header) for header in headers])
        for row in rows:
            sheet.append(
                [
                    spreadsheet_safe_value(row.get(header))
                    for header in headers
                ]
            )
    workbook.save(path)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(
            payload,
            output,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def remove_compliance_export_artifact(path: Path) -> None:
    """Remove only the exact private temporary file created for one response."""

    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
