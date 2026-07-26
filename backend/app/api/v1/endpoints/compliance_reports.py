"""Phase 8 compliance overview and scoped reporting endpoints."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.compliance_enums import (
    ComplianceStatus,
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.compliance_report import (
    ComplianceOverviewResponse,
    ComplianceReportResponse,
    FindingsReportResponse,
)
from app.schemas.finding import FindingFilter
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_report_service import (
    ComplianceReportFilters,
    ComplianceReportService,
    remove_compliance_report_artifact,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ComplianceViewer = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_VIEW)),
]
ComplianceReportViewer = Annotated[
    User,
    Depends(
        require_permissions(
            Permission.COMPLIANCE_VIEW,
            Permission.REPORTS_VIEW,
        )
    ),
]
FindingReportViewer = Annotated[
    User,
    Depends(
        require_permissions(
            Permission.FINDINGS_VIEW,
            Permission.REPORTS_VIEW,
        )
    ),
]


def _service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> ComplianceReportService:
    return ComplianceReportService(
        session,
        settings,
        user,
        metadata,
    )


def _compliance_filters(
    *,
    date_from: date | None,
    date_to: date | None,
    department_id: UUID | None,
    section_id: UUID | None,
    document_type_id: UUID | None,
    validation_rule_id: UUID | None,
    compliance_status: ComplianceStatus | None,
    search: str | None = None,
    sort_by: str = "lastValidated",
    sort_order: Literal["asc", "desc"] = "desc",
) -> ComplianceReportFilters:
    return ComplianceReportFilters(
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        section_id=section_id,
        document_type_id=document_type_id,
        validation_rule_id=validation_rule_id,
        compliance_status=compliance_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/compliance/overview",
    response_model=ApiResponse[ComplianceOverviewResponse],
)
async def compliance_overview(
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    section_id: Annotated[
        UUID | None,
        Query(alias="sectionId"),
    ] = None,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    validation_rule_id: Annotated[
        UUID | None,
        Query(alias="validationRuleId"),
    ] = None,
    compliance_status: Annotated[
        ComplianceStatus | None,
        Query(alias="complianceStatus"),
    ] = None,
) -> ApiResponse[ComplianceOverviewResponse]:
    data = await _service(
        session,
        settings,
        user,
        metadata,
    ).overview(
        _compliance_filters(
            date_from=date_from,
            date_to=date_to,
            department_id=department_id,
            section_id=section_id,
            document_type_id=document_type_id,
            validation_rule_id=validation_rule_id,
            compliance_status=compliance_status,
        )
    )
    return ApiResponse(
        success=True,
        message="Compliance overview retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/reports/compliance",
    response_model=None,
)
async def compliance_report(
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: ComplianceReportViewer,
    metadata: Metadata,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    section_id: Annotated[
        UUID | None,
        Query(alias="sectionId"),
    ] = None,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    validation_rule_id: Annotated[
        UUID | None,
        Query(alias="validationRuleId"),
    ] = None,
    compliance_status: Annotated[
        ComplianceStatus | None,
        Query(alias="complianceStatus"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        str,
        Query(alias="sortBy", min_length=1, max_length=50),
    ] = "lastValidated",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
    export_format: Annotated[
        Literal["json", "xlsx"] | None,
        Query(alias="format"),
    ] = None,
) -> ApiResponse[ComplianceReportResponse] | FileResponse:
    service = _service(session, settings, user, metadata)
    filters = _compliance_filters(
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        section_id=section_id,
        document_type_id=document_type_id,
        validation_rule_id=validation_rule_id,
        compliance_status=compliance_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if export_format is not None:
        artifact = await service.export_compliance_report(
            filters,
            export_format=export_format,
        )
        background_tasks.add_task(
            remove_compliance_report_artifact,
            artifact.path,
        )
        return FileResponse(
            artifact.path,
            media_type=artifact.media_type,
            filename=artifact.filename,
            background=background_tasks,
        )
    data = await service.compliance_report(
        filters,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Compliance report retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/reports/findings",
    response_model=ApiResponse[FindingsReportResponse],
)
async def findings_report(
    session: Session,
    settings: Configuration,
    user: FindingReportViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_id: Annotated[
        UUID | None,
        Query(alias="documentId"),
    ] = None,
    revision_id: Annotated[
        UUID | None,
        Query(alias="revisionId"),
    ] = None,
    compliance_run_id: Annotated[
        UUID | None,
        Query(alias="complianceRunId"),
    ] = None,
    finding_code: Annotated[
        FindingCode | None,
        Query(alias="findingCode"),
    ] = None,
    finding_type: Annotated[
        FindingType | None,
        Query(alias="findingType"),
    ] = None,
    severity: FindingSeverity | None = None,
    finding_status: Annotated[
        FindingStatus | None,
        Query(alias="status"),
    ] = None,
    language_code: Annotated[
        str | None,
        Query(alias="languageCode", max_length=20),
    ] = None,
    assigned_to: Annotated[
        UUID | None,
        Query(alias="assignedTo"),
    ] = None,
    created_by_system: Annotated[
        bool | None,
        Query(alias="createdBySystem"),
    ] = None,
    created_from: Annotated[
        date | None,
        Query(alias="createdFrom"),
    ] = None,
    created_to: Annotated[
        date | None,
        Query(alias="createdTo"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        str,
        Query(alias="sortBy", min_length=1, max_length=50),
    ] = "severity",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> ApiResponse[FindingsReportResponse]:
    service = _service(session, settings, user, metadata)
    start, end = service.finding_date_window(
        created_from,
        created_to,
    )
    data = await service.findings_report(
        FindingFilter(
            search=search,
            department_id=department_id,
            document_id=document_id,
            revision_id=revision_id,
            compliance_run_id=compliance_run_id,
            finding_code=finding_code,
            finding_type=finding_type,
            severity=severity,
            status=finding_status,
            language_code=language_code,
            assigned_to=assigned_to,
            created_by_system=created_by_system,
            created_from=start,
            created_to=end,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )
    return ApiResponse(
        success=True,
        message="Findings report retrieved successfully.",
        data=data,
        errors=None,
    )
