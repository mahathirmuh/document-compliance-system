"""Phase 9 advanced report jobs, snapshots, downloads, and schedules."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshotStatus,
)
from app.models.user import User
from app.schemas.advanced_reporting import (
    AdvancedReportGenerateRequest,
    AdvancedReportJobListResponse,
    AdvancedReportJobResponse,
    ReportScheduleCreateRequest,
    ReportScheduleListResponse,
    ReportScheduleResponse,
    ReportScheduleRunResponse,
    ReportScheduleUpdateRequest,
    ReportSnapshotDeleteResponse,
    ReportSnapshotListResponse,
    ReportSnapshotResponse,
)
from app.schemas.common import ApiResponse
from app.services.auth.auth_service import RequestMetadata
from app.services.reporting.advanced_reporting_service import (
    AdvancedReportingService,
)
from app.services.reporting.report_schedule_service import (
    ReportScheduleService,
)

router = APIRouter(prefix="/reports", tags=["advanced-reports"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ReportViewer = Annotated[
    User, Depends(require_permissions(Permission.ADVANCED_REPORTS_VIEW))
]
ReportExporter = Annotated[
    User, Depends(require_permissions(Permission.ADVANCED_REPORTS_EXPORT))
]
ReportConfigurator = Annotated[
    User,
    Depends(require_permissions(Permission.ADVANCED_REPORTS_CONFIGURE)),
]


@router.post(
    "/generate",
    response_model=ApiResponse[AdvancedReportJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_advanced_report(
    payload: AdvancedReportGenerateRequest,
    session: Session,
    settings: Configuration,
    user: ReportExporter,
    metadata: Metadata,
) -> ApiResponse[AdvancedReportJobResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).generate(payload)
    return ApiResponse(
        success=True,
        message="Advanced report generation has been queued.",
        data=result,
        errors=None,
    )


@router.get(
    "/jobs",
    response_model=ApiResponse[AdvancedReportJobListResponse],
)
async def list_report_jobs(
    session: Session,
    settings: Configuration,
    user: ReportViewer,
    metadata: Metadata,
    report_types: Annotated[
        list[AdvancedReportType] | None, Query(alias="reportType")
    ] = None,
    statuses: Annotated[
        list[ReportJobStatus] | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[AdvancedReportJobListResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).list_jobs(
        report_types=report_types,
        statuses=statuses,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Advanced report jobs retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ApiResponse[AdvancedReportJobResponse],
)
async def get_report_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportViewer,
    metadata: Metadata,
) -> ApiResponse[AdvancedReportJobResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).get_job(job_id)
    return ApiResponse(
        success=True,
        message="Advanced report job retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/snapshots",
    response_model=ApiResponse[ReportSnapshotListResponse],
)
async def list_report_snapshots(
    session: Session,
    settings: Configuration,
    user: ReportViewer,
    metadata: Metadata,
    report_types: Annotated[
        list[AdvancedReportType] | None, Query(alias="reportType")
    ] = None,
    statuses: Annotated[
        list[ReportSnapshotStatus] | None, Query(alias="status")
    ] = None,
    file_formats: Annotated[
        list[ReportFileFormat] | None, Query(alias="format")
    ] = None,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[ReportSnapshotListResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).list_snapshots(
        report_types=report_types,
        statuses=statuses,
        file_formats=file_formats,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Report snapshots retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=ApiResponse[ReportSnapshotResponse],
)
async def get_report_snapshot(
    snapshot_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportViewer,
    metadata: Metadata,
) -> ApiResponse[ReportSnapshotResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).get_snapshot(snapshot_id)
    return ApiResponse(
        success=True,
        message="Report snapshot retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get("/snapshots/{snapshot_id}/download")
async def download_report_snapshot(
    snapshot_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportExporter,
    metadata: Metadata,
) -> StreamingResponse:
    download = await AdvancedReportingService(
        session, settings, user, metadata
    ).prepare_download(snapshot_id)
    return StreamingResponse(
        download.body,
        media_type=download.media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download.filename}"'
            ),
            "Content-Length": str(download.file_size),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/snapshots/{snapshot_id}/delete",
    response_model=ApiResponse[ReportSnapshotDeleteResponse],
)
async def delete_report_snapshot(
    snapshot_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportExporter,
    metadata: Metadata,
) -> ApiResponse[ReportSnapshotDeleteResponse]:
    result = await AdvancedReportingService(
        session, settings, user, metadata
    ).delete(snapshot_id)
    return ApiResponse(
        success=True,
        message="Report snapshot was soft deleted.",
        data=result,
        errors=None,
    )


@router.get(
    "/schedules",
    response_model=ApiResponse[ReportScheduleListResponse],
)
async def list_report_schedules(
    session: Session,
    settings: Configuration,
    user: ReportViewer,
    metadata: Metadata,
    include_inactive: Annotated[
        bool, Query(alias="includeInactive")
    ] = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[ReportScheduleListResponse]:
    result = await ReportScheduleService(
        session, settings, user, metadata
    ).list(
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Report schedules retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/schedules",
    response_model=ApiResponse[ReportScheduleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_report_schedule(
    payload: ReportScheduleCreateRequest,
    session: Session,
    settings: Configuration,
    user: ReportConfigurator,
    metadata: Metadata,
) -> ApiResponse[ReportScheduleResponse]:
    result = await ReportScheduleService(
        session, settings, user, metadata
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Report schedule created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/schedules/{schedule_id}",
    response_model=ApiResponse[ReportScheduleResponse],
)
async def update_report_schedule(
    schedule_id: UUID,
    payload: ReportScheduleUpdateRequest,
    session: Session,
    settings: Configuration,
    user: ReportConfigurator,
    metadata: Metadata,
) -> ApiResponse[ReportScheduleResponse]:
    result = await ReportScheduleService(
        session, settings, user, metadata
    ).update(schedule_id, payload)
    return ApiResponse(
        success=True,
        message="Report schedule updated successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/schedules/{schedule_id}/run",
    response_model=ApiResponse[ReportScheduleRunResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_report_schedule(
    schedule_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportConfigurator,
    metadata: Metadata,
) -> ApiResponse[ReportScheduleRunResponse]:
    result = await ReportScheduleService(
        session, settings, user, metadata
    ).run(schedule_id)
    return ApiResponse(
        success=True,
        message="Report schedule execution has been queued.",
        data=result,
        errors=None,
    )


@router.post(
    "/schedules/{schedule_id}/disable",
    response_model=ApiResponse[ReportScheduleResponse],
)
async def disable_report_schedule(
    schedule_id: UUID,
    session: Session,
    settings: Configuration,
    user: ReportConfigurator,
    metadata: Metadata,
) -> ApiResponse[ReportScheduleResponse]:
    result = await ReportScheduleService(
        session, settings, user, metadata
    ).disable(schedule_id)
    return ApiResponse(
        success=True,
        message="Report schedule disabled successfully.",
        data=result,
        errors=None,
    )
