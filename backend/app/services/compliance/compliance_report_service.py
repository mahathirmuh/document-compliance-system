"""Scoped Phase 8 overview, reports, and bounded report exports."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import ceil
from pathlib import Path
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from sqlalchemy import Select, and_, asc, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.authorization import (
    AuditAction,
    Permission,
    has_permission,
)
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.compliance_enums import (
    ComplianceRunStatus,
    ComplianceStatus,
    FindingSeverity,
    FindingStatus,
)
from app.models.compliance_run import ComplianceRun
from app.models.department import Department
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.document_type import DocumentType
from app.models.section import Section
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.models.validation_rule import ValidationRule
from app.schemas.compliance_report import (
    ComplianceBreakdownItem,
    ComplianceLanguageCount,
    ComplianceOverviewResponse,
    ComplianceReportItem,
    ComplianceReportResponse,
    ComplianceSectionCount,
    ComplianceTrendItem,
    FindingCountItem,
    FindingsReportResponse,
    FindingsReportSummary,
    FindingTrendItem,
)
from app.schemas.finding import (
    FindingFilter,
    FindingListResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_export_service import (
    spreadsheet_safe_value,
)
from app.services.compliance.findings.finding_management_service import (
    finding_list_item,
)
from app.services.documents.base import DocumentServiceBase, document_error
from app.utils.datetime import utc_now

_OPEN_FINDING_STATUSES = frozenset(
    {
        FindingStatus.OPEN,
        FindingStatus.IN_REVIEW,
        FindingStatus.REOPENED,
    }
)
_PRESENCE_STATES = frozenset(
    {
        "PRESENT",
        "NOT_PRESENT",
        "INSUFFICIENT_EVIDENCE",
        "MIXED_ONLY",
    }
)
_COMPLIANCE_SORT_FIELDS = {
    "lastValidated": func.coalesce(
        ComplianceRun.completed_at,
        ComplianceRun.created_at,
    ),
    "last_validated": func.coalesce(
        ComplianceRun.completed_at,
        ComplianceRun.created_at,
    ),
    "score": ComplianceRun.compliance_score,
    "complianceStatus": ComplianceRun.compliance_status,
    "compliance_status": ComplianceRun.compliance_status,
    "documentCode": DocumentRevision.full_document_code,
    "document_code": DocumentRevision.full_document_code,
    "title": Document.title,
    "department": Department.name,
    "documentType": DocumentType.name,
    "document_type": DocumentType.name,
}
_FINDING_SORT_FIELDS = {
    "createdAt": ValidationFinding.created_at,
    "created_at": ValidationFinding.created_at,
    "findingCode": ValidationFinding.finding_code,
    "finding_code": ValidationFinding.finding_code,
    "status": ValidationFinding.status,
    "title": ValidationFinding.title,
    "updatedAt": ValidationFinding.updated_at,
    "updated_at": ValidationFinding.updated_at,
}
_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@dataclass(frozen=True, slots=True)
class ComplianceReportFilters:
    """Validated filters shared by overview, report, and export."""

    date_from: date | None = None
    date_to: date | None = None
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    validation_rule_id: UUID | None = None
    compliance_status: ComplianceStatus | None = None
    search: str | None = None
    sort_by: str = "lastValidated"
    sort_order: Literal["asc", "desc"] = "desc"


@dataclass(frozen=True, slots=True)
class ComplianceReportArtifact:
    """Private temporary report file returned through ``FileResponse``."""

    path: Path
    filename: str
    media_type: str


class ComplianceReportService(DocumentServiceBase):
    """Read report projections without re-running compliance validation."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings

    async def overview(
        self,
        filters: ComplianceReportFilters,
    ) -> ComplianceOverviewResponse:
        """Return latest-official-run metrics inside the caller's scope."""

        self._ensure_permission(Permission.COMPLIANCE_VIEW)
        predicates = self._compliance_predicates(filters)
        statement = (
            select(
                ComplianceRun.id,
                ComplianceRun.compliance_status,
                ComplianceRun.compliance_score,
                ComplianceRun.missing_languages_json,
                ComplianceRun.missing_sections_json,
                ComplianceRun.completed_at,
                ComplianceRun.created_at,
                Department.name.label("department_name"),
                DocumentType.name.label("document_type_name"),
            )
            .select_from(ComplianceRun)
            .join(
                DocumentFile,
                and_(
                    DocumentFile.id
                    == ComplianceRun.document_file_id,
                    DocumentFile.latest_compliance_run_id
                    == ComplianceRun.id,
                ),
            )
            .join(Document, Document.id == ComplianceRun.document_id)
            .join(Department, Department.id == Document.department_id)
            .join(
                DocumentType,
                DocumentType.id == Document.document_type_id,
            )
            .where(*predicates)
        )
        rows = (await self.session.execute(statement)).all()

        status_counts: Counter[ComplianceStatus] = Counter()
        department_counts: dict[
            str, Counter[ComplianceStatus]
        ] = defaultdict(Counter)
        document_type_counts: dict[
            str, Counter[ComplianceStatus]
        ] = defaultdict(Counter)
        missing_languages: Counter[str] = Counter()
        missing_sections: Counter[str] = Counter()
        trend_scores: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            status = ComplianceStatus(row.compliance_status)
            status_counts[status] += 1
            department_counts[row.department_name][status] += 1
            document_type_counts[row.document_type_name][status] += 1
            missing_languages.update(
                _string_list(row.missing_languages_json)
            )
            missing_sections.update(
                code.upper()
                for code in _string_list(row.missing_sections_json)
            )
            validated_at = row.completed_at or row.created_at
            trend_scores[validated_at.strftime("%Y-%m")].append(
                float(row.compliance_score)
            )

        finding_counts, open_critical, open_major = (
            await self._overview_findings(predicates)
        )
        return ComplianceOverviewResponse(
            total_validated_documents=len(rows),
            compliant=status_counts[ComplianceStatus.COMPLIANT],
            partially_compliant=status_counts[
                ComplianceStatus.PARTIALLY_COMPLIANT
            ],
            non_compliant=status_counts[
                ComplianceStatus.NON_COMPLIANT
            ],
            needs_review=status_counts[ComplianceStatus.NEEDS_REVIEW],
            not_evaluated=status_counts[
                ComplianceStatus.NOT_EVALUATED
            ],
            open_critical_findings=open_critical,
            open_major_findings=open_major,
            by_department=_breakdown_items(department_counts),
            by_document_type=_breakdown_items(document_type_counts),
            trend=[
                ComplianceTrendItem(
                    period=period,
                    score=round(sum(scores) / len(scores), 2),
                    validated=len(scores),
                )
                for period, scores in sorted(trend_scores.items())
            ],
            findings_by_severity={
                severity.value.lower(): finding_counts[severity]
                for severity in FindingSeverity
            },
            missing_languages=[
                ComplianceLanguageCount(
                    language_code=language,
                    count=count,
                )
                for language, count in sorted(
                    missing_languages.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
            missing_sections=[
                ComplianceSectionCount(
                    canonical_code=canonical,
                    count=count,
                )
                for canonical, count in sorted(
                    missing_sections.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
        )

    async def compliance_report(
        self,
        filters: ComplianceReportFilters,
        *,
        page: int,
        page_size: int,
    ) -> ComplianceReportResponse:
        """Return one page of document-level latest compliance results."""

        self._ensure_permission(Permission.COMPLIANCE_VIEW)
        self._ensure_permission(Permission.REPORTS_VIEW)
        statement = self._compliance_report_statement(filters)
        total = await self._statement_count(statement)
        ordered = self._sort_compliance_statement(
            statement,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        rows = (
            await self.session.execute(
                ordered.offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        return ComplianceReportResponse(
            items=[_compliance_report_item(*row) for row in rows],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def export_compliance_report(
        self,
        filters: ComplianceReportFilters,
        *,
        export_format: Literal["json", "xlsx"],
    ) -> ComplianceReportArtifact:
        """Create a bounded private artifact and audit the export."""

        self._ensure_permission(Permission.COMPLIANCE_VIEW)
        self._ensure_permission(Permission.REPORTS_VIEW)
        self._ensure_permission(Permission.COMPLIANCE_EXPORT)
        self._ensure_permission(Permission.REPORTS_EXPORT)
        statement = self._compliance_report_statement(filters)
        total = await self._statement_count(statement)
        maximum = self.settings.compliance_export_max_rows
        if total > maximum:
            raise document_error(
                (
                    "The compliance report contains more rows than the "
                    "configured export limit."
                ),
                code="COMPLIANCE_REPORT_EXPORT_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance report is too large to export.",
            )
        ordered = self._sort_compliance_statement(
            statement,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        rows = (await self.session.execute(ordered.limit(maximum))).all()
        items = [_compliance_report_item(*row) for row in rows]

        descriptor, raw_path = tempfile.mkstemp(
            prefix="compliance-report-",
            suffix=f".{export_format}",
        )
        os.close(descriptor)
        path = Path(raw_path)
        try:
            if export_format == "json":
                await asyncio.to_thread(
                    _write_compliance_json,
                    path,
                    items,
                )
                media_type = "application/json"
            else:
                await asyncio.to_thread(
                    _write_compliance_xlsx,
                    path,
                    items,
                )
                media_type = _XLSX_MEDIA_TYPE
            await self.audit(
                action=AuditAction.EXPORT_COMPLIANCE_RESULT,
                entity_type="ComplianceReport",
                entity_id=None,
                description="Latest compliance report exported.",
                new_values={
                    "format": export_format,
                    "rowCount": len(items),
                    "filters": _audit_filters(filters),
                    "latestOfficialRunsOnly": True,
                    "structuralValidationOnly": True,
                    "semanticSimilarityEvaluated": False,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            remove_compliance_report_artifact(path)
            raise
        generated = utc_now()
        return ComplianceReportArtifact(
            path=path,
            filename=(
                f"compliance-report-{generated:%Y-%m-%d_%H-%M}."
                f"{export_format}"
            ),
            media_type=media_type,
        )

    async def findings_report(
        self,
        filters: FindingFilter,
    ) -> FindingsReportResponse:
        """Return workflow summary and a scoped page of current findings."""

        self._ensure_permission(Permission.FINDINGS_VIEW)
        self._ensure_permission(Permission.REPORTS_VIEW)
        predicates = self._finding_predicates(filters)
        summary_rows = (
            await self.session.execute(
                select(
                    ValidationFinding.status,
                    ValidationFinding.severity,
                    ValidationFinding.finding_type,
                    ValidationFinding.created_at,
                    Department.name,
                )
                .select_from(ValidationFinding)
                .join(
                    Document,
                    Document.id == ValidationFinding.document_id,
                )
                .join(
                    Department,
                    Department.id == Document.department_id,
                )
                .join(
                    DocumentFile,
                    DocumentFile.id
                    == ValidationFinding.document_file_id,
                )
                .where(*predicates)
            )
        ).all()
        summary = _findings_summary(summary_rows)
        total = summary.total_findings
        statement = (
            select(ValidationFinding)
            .join(
                Document,
                Document.id == ValidationFinding.document_id,
            )
            .join(
                DocumentFile,
                DocumentFile.id == ValidationFinding.document_file_id,
            )
            .options(
                selectinload(ValidationFinding.document).selectinload(
                    Document.department
                ),
                selectinload(ValidationFinding.revision),
                selectinload(ValidationFinding.validation_rule),
                selectinload(ValidationFinding.detected_section),
                selectinload(ValidationFinding.assignee),
            )
            .where(*predicates)
        )
        ordered = self._sort_findings_statement(
            statement,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        findings = list(
            (
                await self.session.scalars(
                    ordered.offset(
                        (filters.page - 1) * filters.page_size
                    ).limit(filters.page_size)
                )
            ).all()
        )
        return FindingsReportResponse(
            summary=summary,
            findings=FindingListResponse(
                items=[finding_list_item(item) for item in findings],
                page=filters.page,
                pageSize=filters.page_size,
                totalItems=total,
                totalPages=(
                    ceil(total / filters.page_size) if total else 0
                ),
            ),
        )

    def finding_date_window(
        self,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        """Convert UI dates to an inclusive, application-timezone window."""

        start, end_exclusive = self._date_bounds(date_from, date_to)
        return (
            start,
            (
                end_exclusive - timedelta(microseconds=1)
                if end_exclusive is not None
                else None
            ),
        )

    async def _overview_findings(
        self,
        compliance_predicates: list[Any],
    ) -> tuple[Counter[FindingSeverity], int, int]:
        latest_run_ids = (
            select(ComplianceRun.id)
            .select_from(ComplianceRun)
            .join(
                DocumentFile,
                and_(
                    DocumentFile.id
                    == ComplianceRun.document_file_id,
                    DocumentFile.latest_compliance_run_id
                    == ComplianceRun.id,
                ),
            )
            .join(Document, Document.id == ComplianceRun.document_id)
            .where(*compliance_predicates)
        )
        rows = (
            await self.session.execute(
                select(
                    ValidationFinding.severity,
                    ValidationFinding.status,
                    func.count(ValidationFinding.id),
                )
                .where(
                    ValidationFinding.compliance_run_id.in_(
                        latest_run_ids
                    )
                )
                .group_by(
                    ValidationFinding.severity,
                    ValidationFinding.status,
                )
            )
        ).all()
        severity_counts: Counter[FindingSeverity] = Counter()
        open_critical = 0
        open_major = 0
        for severity_raw, status_raw, count_raw in rows:
            severity = FindingSeverity(severity_raw)
            status = FindingStatus(status_raw)
            count = int(count_raw)
            severity_counts[severity] += count
            if status in _OPEN_FINDING_STATUSES:
                if severity is FindingSeverity.CRITICAL:
                    open_critical += count
                elif severity is FindingSeverity.MAJOR:
                    open_major += count
        return severity_counts, open_critical, open_major

    def _compliance_report_statement(
        self,
        filters: ComplianceReportFilters,
    ):
        return (
            select(
                ComplianceRun,
                Document,
                Department,
                Section,
                DocumentType,
                DocumentRevision,
                ValidationRule,
            )
            .select_from(ComplianceRun)
            .join(
                DocumentFile,
                and_(
                    DocumentFile.id
                    == ComplianceRun.document_file_id,
                    DocumentFile.latest_compliance_run_id
                    == ComplianceRun.id,
                ),
            )
            .join(Document, Document.id == ComplianceRun.document_id)
            .join(Department, Department.id == Document.department_id)
            .outerjoin(Section, Section.id == Document.section_id)
            .join(
                DocumentType,
                DocumentType.id == Document.document_type_id,
            )
            .join(
                DocumentRevision,
                DocumentRevision.id
                == ComplianceRun.document_revision_id,
            )
            .join(
                ValidationRule,
                ValidationRule.id == ComplianceRun.validation_rule_id,
            )
            .where(*self._compliance_predicates(filters))
        )

    def _compliance_predicates(
        self,
        filters: ComplianceReportFilters,
    ) -> list[Any]:
        start, end_exclusive = self._date_bounds(
            filters.date_from,
            filters.date_to,
        )
        department_ids = self._scope_department_ids(
            filters.department_id
        )
        validated_at = func.coalesce(
            ComplianceRun.completed_at,
            ComplianceRun.created_at,
        )
        predicates: list[Any] = [
            ComplianceRun.status.in_(
                (
                    ComplianceRunStatus.COMPLETED,
                    ComplianceRunStatus.PARTIALLY_COMPLETED,
                )
            )
        ]
        if department_ids is not None:
            predicates.append(
                Document.department_id.in_(department_ids)
            )
        optional_filters = (
            (filters.section_id, Document.section_id),
            (filters.document_type_id, Document.document_type_id),
            (
                filters.validation_rule_id,
                ComplianceRun.validation_rule_id,
            ),
            (
                filters.compliance_status,
                ComplianceRun.compliance_status,
            ),
        )
        predicates.extend(
            column == value
            for value, column in optional_filters
            if value is not None
        )
        if start is not None:
            predicates.append(validated_at >= start)
        if end_exclusive is not None:
            predicates.append(validated_at < end_exclusive)
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            predicates.append(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    DocumentRevision.full_document_code.ilike(pattern),
                )
            )
        return predicates

    def _finding_predicates(
        self,
        filters: FindingFilter,
    ) -> list[Any]:
        if (
            filters.created_from is not None
            and filters.created_to is not None
            and filters.created_to < filters.created_from
        ):
            raise document_error(
                "createdTo must be greater than or equal to createdFrom.",
                field="createdTo",
                code="FINDING_REPORT_DATE_RANGE_INVALID",
                title="Finding report filter is invalid.",
            )
        department_ids = self._scope_department_ids(
            filters.department_id
        )
        predicates: list[Any] = [
            or_(
                ValidationFinding.is_system_generated.is_(False),
                DocumentFile.latest_compliance_run_id
                == ValidationFinding.compliance_run_id,
            )
        ]
        if department_ids is not None:
            predicates.append(
                Document.department_id.in_(department_ids)
            )
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            predicates.append(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    ValidationFinding.title.ilike(pattern),
                    ValidationFinding.description.ilike(pattern),
                    ValidationFinding.source_reference.ilike(pattern),
                )
            )
        optional_filters = (
            (filters.document_id, ValidationFinding.document_id),
            (
                filters.revision_id,
                ValidationFinding.document_revision_id,
            ),
            (
                filters.compliance_run_id,
                ValidationFinding.compliance_run_id,
            ),
            (filters.finding_code, ValidationFinding.finding_code),
            (filters.finding_type, ValidationFinding.finding_type),
            (filters.severity, ValidationFinding.severity),
            (filters.status, ValidationFinding.status),
            (filters.language_code, ValidationFinding.language_code),
            (filters.assigned_to, ValidationFinding.assigned_to),
        )
        predicates.extend(
            column == value
            for value, column in optional_filters
            if value is not None
        )
        if filters.created_by_system is not None:
            predicates.append(
                ValidationFinding.is_system_generated.is_(
                    filters.created_by_system
                )
            )
        if filters.created_from is not None:
            predicates.append(
                ValidationFinding.created_at >= filters.created_from
            )
        if filters.created_to is not None:
            predicates.append(
                ValidationFinding.created_at <= filters.created_to
            )
        return predicates

    def _scope_department_ids(
        self,
        requested: UUID | None,
    ) -> list[UUID] | None:
        if has_permission(
            self.user.role,
            Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        ):
            return [requested] if requested is not None else None
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department assignment is required for report access."
            )
        if (
            requested is not None
            and requested != self.user.department_id
        ):
            raise AuthorizationError(
                "The requested department is outside your report scope."
            )
        return [self.user.department_id]

    def _date_bounds(
        self,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        if (
            date_from is not None
            and date_to is not None
            and date_to < date_from
        ):
            raise document_error(
                "dateTo must be greater than or equal to dateFrom.",
                field="dateTo",
                code="COMPLIANCE_REPORT_DATE_RANGE_INVALID",
                title="Compliance report filter is invalid.",
            )
        timezone = ZoneInfo(self.settings.application_timezone)
        start = (
            datetime.combine(date_from, time.min, tzinfo=timezone)
            if date_from is not None
            else None
        )
        end_exclusive = (
            datetime.combine(
                date_to + timedelta(days=1),
                time.min,
                tzinfo=timezone,
            )
            if date_to is not None
            else None
        )
        return start, end_exclusive

    async def _statement_count(
        self,
        statement: Select[Any],
    ) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )

    @staticmethod
    def _sort_compliance_statement(
        statement: Select[Any],
        *,
        sort_by: str,
        sort_order: str,
    ) -> Select[Any]:
        column = _COMPLIANCE_SORT_FIELDS.get(sort_by.strip())
        if column is None:
            raise document_error(
                "sortBy is not a supported compliance report field.",
                field="sortBy",
                code="COMPLIANCE_REPORT_SORT_FIELD_INVALID",
                title="Compliance report sort is invalid.",
            )
        direction = sort_order.strip().lower()
        if direction not in {"asc", "desc"}:
            raise document_error(
                "sortOrder must be either asc or desc.",
                field="sortOrder",
                code="COMPLIANCE_REPORT_SORT_ORDER_INVALID",
                title="Compliance report sort is invalid.",
            )
        ordering = asc if direction == "asc" else desc
        return statement.order_by(
            ordering(column),
            desc(ComplianceRun.id),
        )

    @staticmethod
    def _sort_findings_statement(
        statement: Select[Any],
        *,
        sort_by: str,
        sort_order: str,
    ) -> Select[Any]:
        direction = sort_order.strip().lower()
        if direction not in {"asc", "desc"}:
            raise document_error(
                "sortOrder must be either asc or desc.",
                field="sortOrder",
                code="FINDING_REPORT_SORT_ORDER_INVALID",
                title="Finding report sort is invalid.",
            )
        ordering = asc if direction == "asc" else desc
        if sort_by.strip() == "severity":
            severity_rank = case(
                (
                    ValidationFinding.severity
                    == FindingSeverity.CRITICAL,
                    4,
                ),
                (
                    ValidationFinding.severity == FindingSeverity.MAJOR,
                    3,
                ),
                (
                    ValidationFinding.severity == FindingSeverity.MINOR,
                    2,
                ),
                else_=1,
            )
            return statement.order_by(
                ordering(severity_rank),
                desc(ValidationFinding.created_at),
                desc(ValidationFinding.id),
            )
        column = _FINDING_SORT_FIELDS.get(sort_by.strip())
        if column is None:
            raise document_error(
                "sortBy is not a supported finding report field.",
                field="sortBy",
                code="FINDING_REPORT_SORT_FIELD_INVALID",
                title="Finding report sort is invalid.",
            )
        return statement.order_by(
            ordering(column),
            desc(ValidationFinding.id),
        )

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()


def _compliance_report_item(
    run: ComplianceRun,
    document: Document,
    department: Department,
    section: Section | None,
    document_type: DocumentType,
    revision: DocumentRevision,
    validation_rule: ValidationRule,
) -> ComplianceReportItem:
    rule_snapshot = _mapping(run.rule_snapshot_json)
    snapshot_rule_name = _nonempty_text(
        rule_snapshot.get("ruleName")
        or rule_snapshot.get("rule_name")
    )
    snapshot_rule_code = _nonempty_text(
        rule_snapshot.get("ruleCode")
        or rule_snapshot.get("rule_code")
    )
    return ComplianceReportItem(
        run_id=run.id,
        document_id=document.id,
        document_file_id=run.document_file_id,
        document_code=revision.full_document_code,
        title=document.title,
        department=department.name,
        section=section.name if section is not None else None,
        document_type=document_type.name,
        revision=revision.revision_code,
        validation_rule=(
            snapshot_rule_name
            or snapshot_rule_code
            or validation_rule.name
        ),
        language_presence=_language_presence(run),
        section_completeness=_section_completeness(run),
        language_order_valid=_language_order_valid(run),
        score=float(run.compliance_score),
        compliance_status=run.compliance_status,
        critical_findings=run.critical_findings,
        major_findings=run.major_findings,
        last_validated=run.completed_at or run.created_at,
    )


def _language_presence(run: ComplianceRun) -> dict[str, str]:
    validators = _mapping(run.metrics_json.get("validators"))
    metrics = _mapping(
        _mapping(validators.get("LANGUAGE_PRESENCE")).get("metrics")
    )
    stored = _mapping(metrics.get("presence"))
    detected = set(_string_list(run.detected_languages_json))
    missing = set(_string_list(run.missing_languages_json))
    presence: dict[str, str] = {}
    for language in ("id", "en", "zh"):
        raw = str(stored.get(language, "")).upper()
        if raw in _PRESENCE_STATES:
            presence[language] = raw
        elif language in detected:
            presence[language] = "PRESENT"
        elif language in missing:
            presence[language] = "NOT_PRESENT"
        else:
            presence[language] = "NOT_PRESENT"
    return presence


def _section_completeness(run: ComplianceRun) -> float:
    validators = _mapping(run.metrics_json.get("validators"))
    metrics = _mapping(
        _mapping(validators.get("REQUIRED_SECTIONS")).get("metrics")
    )
    total = _integer(metrics.get("totalRequiredSections"))
    complete = _integer(metrics.get("completeSections"))
    if total is None:
        total = len(_string_list(run.required_sections_json))
        complete = total - len(_string_list(run.missing_sections_json))
    if total <= 0:
        return 100.0
    return round(
        max(0.0, min(100.0, (complete or 0) / total * 100)),
        2,
    )


def _language_order_valid(run: ComplianceRun) -> bool | None:
    validators = _mapping(run.metrics_json.get("validators"))
    result = _mapping(validators.get("LANGUAGE_ORDER"))
    metrics = _mapping(result.get("metrics"))
    evaluated = _integer(metrics.get("evaluatedGroups"))
    invalid = _integer(metrics.get("invalidGroups"))
    if not evaluated:
        return None
    return (invalid or 0) == 0


def _findings_summary(rows: Sequence[Any]) -> FindingsReportSummary:
    status_counts: Counter[FindingStatus] = Counter()
    severity_counts: Counter[FindingSeverity] = Counter()
    department_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    trend_counts: Counter[str] = Counter()
    for row in rows:
        status_counts[FindingStatus(row.status)] += 1
        severity_counts[FindingSeverity(row.severity)] += 1
        department_counts[row.name] += 1
        type_counts[str(row.finding_type)] += 1
        trend_counts[row.created_at.strftime("%Y-%m")] += 1
    return FindingsReportSummary(
        total_findings=len(rows),
        open=(
            status_counts[FindingStatus.OPEN]
            + status_counts[FindingStatus.REOPENED]
        ),
        in_review=status_counts[FindingStatus.IN_REVIEW],
        resolved=(
            status_counts[FindingStatus.RESOLVED]
            + status_counts[FindingStatus.CLOSED]
        ),
        critical=severity_counts[FindingSeverity.CRITICAL],
        major=severity_counts[FindingSeverity.MAJOR],
        minor=severity_counts[FindingSeverity.MINOR],
        information=severity_counts[FindingSeverity.INFORMATION],
        false_positive=status_counts[FindingStatus.FALSE_POSITIVE],
        accepted_risk=status_counts[FindingStatus.ACCEPTED_RISK],
        by_department=_count_items(department_counts),
        by_type=_count_items(type_counts),
        by_severity=[
            FindingCountItem(
                label=severity.value,
                count=severity_counts[severity],
            )
            for severity in FindingSeverity
        ],
        trend=[
            FindingTrendItem(period=period, count=count)
            for period, count in sorted(trend_counts.items())
        ],
    )


def _breakdown_items(
    groups: dict[str, Counter[ComplianceStatus]],
) -> list[ComplianceBreakdownItem]:
    output: list[ComplianceBreakdownItem] = []
    for label, counts in groups.items():
        output.append(
            ComplianceBreakdownItem(
                label=label,
                total=sum(counts.values()),
                compliant=counts[ComplianceStatus.COMPLIANT],
                partially_compliant=counts[
                    ComplianceStatus.PARTIALLY_COMPLIANT
                ],
                non_compliant=counts[
                    ComplianceStatus.NON_COMPLIANT
                ],
                needs_review=counts[ComplianceStatus.NEEDS_REVIEW],
                not_evaluated=counts[
                    ComplianceStatus.NOT_EVALUATED
                ],
            )
        )
    return sorted(output, key=lambda item: (-item.total, item.label.casefold()))


def _count_items(counter: Counter[str]) -> list[FindingCountItem]:
    return [
        FindingCountItem(label=label, count=count)
        for label, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        )
    ]


def _write_compliance_json(
    path: Path,
    items: list[ComplianceReportItem],
) -> None:
    payload = {
        "generatedAt": utc_now().isoformat(),
        "latestOfficialRunsOnly": True,
        "structuralValidationOnly": True,
        "semanticSimilarityEvaluated": False,
        "totalItems": len(items),
        "items": [
            item.model_dump(mode="json", by_alias=True)
            for item in items
        ],
    }
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(
            payload,
            output,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def _write_compliance_xlsx(
    path: Path,
    items: list[ComplianceReportItem],
) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Compliance")
    headers = (
        "Document Code",
        "Title",
        "Department",
        "Section",
        "Document Type",
        "Revision",
        "Validation Rule",
        "Indonesian",
        "English",
        "Chinese",
        "Section Completeness (%)",
        "Language Order Valid",
        "Score",
        "Compliance Status",
        "Critical Findings",
        "Major Findings",
        "Last Validated",
        "Structural Validation Only",
        "Semantic Similarity Evaluated",
    )
    sheet.append([spreadsheet_safe_value(value) for value in headers])
    for item in items:
        sheet.append(
            [
                spreadsheet_safe_value(item.document_code),
                spreadsheet_safe_value(item.title),
                spreadsheet_safe_value(item.department),
                spreadsheet_safe_value(item.section),
                spreadsheet_safe_value(item.document_type),
                spreadsheet_safe_value(item.revision),
                spreadsheet_safe_value(item.validation_rule),
                spreadsheet_safe_value(item.language_presence["id"]),
                spreadsheet_safe_value(item.language_presence["en"]),
                spreadsheet_safe_value(item.language_presence["zh"]),
                item.section_completeness,
                item.language_order_valid,
                item.score,
                item.compliance_status.value,
                item.critical_findings,
                item.major_findings,
                item.last_validated.isoformat(),
                True,
                False,
            ]
        )
    workbook.save(path)


def remove_compliance_report_artifact(path: Path) -> None:
    """Remove only the exact private temporary file made for one response."""

    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _mapping(value: object) -> dict[str, object]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, dict)
        else {}
    )


def _nonempty_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [str(key) for key, item in value.items() if item]
    return []


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _audit_filters(
    filters: ComplianceReportFilters,
) -> dict[str, object]:
    return {
        "dateFrom": (
            filters.date_from.isoformat()
            if filters.date_from is not None
            else None
        ),
        "dateTo": (
            filters.date_to.isoformat()
            if filters.date_to is not None
            else None
        ),
        "departmentId": _uuid_string(filters.department_id),
        "sectionId": _uuid_string(filters.section_id),
        "documentTypeId": _uuid_string(filters.document_type_id),
        "validationRuleId": _uuid_string(
            filters.validation_rule_id
        ),
        "complianceStatus": (
            filters.compliance_status.value
            if filters.compliance_status is not None
            else None
        ),
        "search": filters.search,
        "sortBy": filters.sort_by,
        "sortOrder": filters.sort_order,
    }


def _uuid_string(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
