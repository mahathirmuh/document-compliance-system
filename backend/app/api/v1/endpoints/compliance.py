"""Phase 8 compliance validation jobs, retained results, and exports."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.compliance_enums import ComplianceJobStatus, ComplianceStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.compliance import (
    ComplianceCancelResponse,
    ComplianceComparisonResponse,
    ComplianceJobListResponse,
    ComplianceJobResponse,
    ComplianceQueuedResponse,
    ComplianceRevalidateRequest,
    ComplianceRunListResponse,
    ComplianceRunResponse,
    ComplianceScoreBreakdownResponse,
    ComplianceStartRequest,
    ComplianceSummaryResponse,
)
from app.schemas.finding import FindingListResponse
from app.schemas.section_detection import DetectedSectionListResponse
from app.schemas.translation_group import TranslationGroupListResponse
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_job_service import (
    ComplianceJobService,
)
from app.services.compliance.compliance_query_service import (
    ComplianceQueryService,
)
from app.services.compliance.compliance_result_export_service import (
    ComplianceResultExportService,
    remove_compliance_export_artifact,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ComplianceViewer = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_VIEW)),
]
ComplianceValidator = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_VALIDATE)),
]
ComplianceRevalidator = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_REVALIDATE)),
]
ComplianceExporter = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_EXPORT)),
]


def _job_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> ComplianceJobService:
    return ComplianceJobService(session, settings, user, metadata)


def _query_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> ComplianceQueryService:
    return ComplianceQueryService(session, settings, user, metadata)


@router.post(
    "/compliance/jobs",
    response_model=ApiResponse[ComplianceQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_compliance_validation(
    payload: ComplianceStartRequest,
    session: Session,
    settings: Configuration,
    user: ComplianceValidator,
    metadata: Metadata,
) -> ApiResponse[ComplianceQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).start(
        document_file_id=payload.document_file_id,
        extraction_run_id=payload.extraction_run_id,
        ocr_run_id=payload.ocr_run_id,
        language_detection_run_id=payload.language_detection_run_id,
        validation_rule_id=payload.validation_rule_id,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "An equivalent compliance result was reused."
            if data.reused_existing_result
            else "Compliance validation has been queued."
        ),
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/jobs",
    response_model=ApiResponse[ComplianceJobListResponse],
)
async def list_compliance_jobs(
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_id: Annotated[UUID | None, Query(alias="documentId")] = None,
    revision_id: Annotated[UUID | None, Query(alias="revisionId")] = None,
    document_file_id: Annotated[
        UUID | None,
        Query(alias="documentFileId"),
    ] = None,
    validation_rule_id: Annotated[
        UUID | None,
        Query(alias="validationRuleId"),
    ] = None,
    compliance_status: Annotated[
        ComplianceStatus | None,
        Query(alias="complianceStatus"),
    ] = None,
    statuses: Annotated[
        list[ComplianceJobStatus] | None,
        Query(alias="status"),
    ] = None,
    requested_by: Annotated[
        UUID | None,
        Query(alias="requestedBy"),
    ] = None,
    requested_from: Annotated[
        datetime | None,
        Query(alias="requestedFrom"),
    ] = None,
    requested_to: Annotated[
        datetime | None,
        Query(alias="requestedTo"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal["requestedAt", "completedAt", "status", "progress"],
        Query(alias="sortBy"),
    ] = "requestedAt",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> ApiResponse[ComplianceJobListResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).list(
        search=search,
        department_id=department_id,
        document_id=document_id,
        revision_id=revision_id,
        document_file_id=document_file_id,
        validation_rule_id=validation_rule_id,
        compliance_status=compliance_status,
        requested_by=requested_by,
        statuses=statuses,
        requested_from=requested_from,
        requested_to=requested_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Compliance jobs retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/jobs/{job_id}",
    response_model=ApiResponse[ComplianceJobResponse],
)
async def get_compliance_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceJobResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).get(job_id)
    return ApiResponse(
        success=True,
        message="Compliance job retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/compliance/jobs/{job_id}/cancel",
    response_model=ApiResponse[ComplianceCancelResponse],
)
async def cancel_compliance_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceValidator,
    metadata: Metadata,
) -> ApiResponse[ComplianceCancelResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Compliance cancellation has been requested.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}",
    response_model=ApiResponse[ComplianceRunResponse],
)
async def get_compliance_run(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceRunResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).get_run(run_id)
    return ApiResponse(
        success=True,
        message="Compliance result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/summary",
    response_model=ApiResponse[ComplianceSummaryResponse],
)
async def get_compliance_summary(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceSummaryResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).summary(run_id)
    return ApiResponse(
        success=True,
        message="Compliance summary retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/score-breakdown",
    response_model=ApiResponse[ComplianceScoreBreakdownResponse],
)
async def get_compliance_score_breakdown(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceScoreBreakdownResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).score_breakdown(run_id)
    return ApiResponse(
        success=True,
        message="Compliance score breakdown retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/sections",
    response_model=ApiResponse[DetectedSectionListResponse],
)
async def list_compliance_sections(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[DetectedSectionListResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).list_sections(
        run_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Detected sections retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/translation-groups",
    response_model=ApiResponse[TranslationGroupListResponse],
)
async def list_compliance_translation_groups(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    container_id: Annotated[
        UUID | None,
        Query(alias="containerId"),
    ] = None,
    detected_section_id: Annotated[
        UUID | None,
        Query(alias="detectedSectionId"),
    ] = None,
    is_complete: Annotated[
        bool | None,
        Query(alias="isComplete"),
    ] = None,
    is_order_valid: Annotated[
        bool | None,
        Query(alias="isOrderValid"),
    ] = None,
    low_confidence: Annotated[
        bool | None,
        Query(alias="lowConfidence"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 500,
) -> ApiResponse[TranslationGroupListResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).list_translation_groups(
        run_id,
        container_id=container_id,
        detected_section_id=detected_section_id,
        is_complete=is_complete,
        is_order_valid=is_order_valid,
        low_confidence=low_confidence,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Translation groups retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/findings",
    response_model=ApiResponse[FindingListResponse],
)
async def list_compliance_run_findings(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[FindingListResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).list_run_findings(
        run_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Compliance findings retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/compliance/runs/{run_id}/export")
async def export_compliance_result(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: ComplianceExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "xlsx"],
        Query(alias="format"),
    ] = "json",
) -> FileResponse:
    artifact = await ComplianceResultExportService(
        session,
        settings,
        user,
        metadata,
    ).export(run_id, export_format=export_format)
    background_tasks.add_task(
        remove_compliance_export_artifact,
        Path(artifact.path),
    )
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        filename=artifact.filename,
        background=background_tasks,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.post(
    "/compliance/runs/{run_id}/revalidate",
    response_model=ApiResponse[ComplianceQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def revalidate_compliance(
    run_id: UUID,
    payload: ComplianceRevalidateRequest,
    session: Session,
    settings: Configuration,
    user: ComplianceRevalidator,
    metadata: Metadata,
) -> ApiResponse[ComplianceQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).revalidate(
        run_id,
        reason=payload.reason,
        validation_rule_id=payload.validation_rule_id,
    )
    return ApiResponse(
        success=True,
        message="Compliance revalidation has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/compliance/runs/{run_id}/compare/{other_run_id}",
    response_model=ApiResponse[ComplianceComparisonResponse],
)
async def compare_compliance_runs(
    run_id: UUID,
    other_run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceComparisonResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).compare(run_id, other_run_id)
    return ApiResponse(
        success=True,
        message="Compliance comparison retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/compliance",
    response_model=ApiResponse[ComplianceRunResponse],
)
async def get_latest_file_compliance(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
) -> ApiResponse[ComplianceRunResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).latest_for_file(file_id)
    return ApiResponse(
        success=True,
        message="Latest compliance result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/compliance-history",
    response_model=ApiResponse[ComplianceRunListResponse],
)
async def get_file_compliance_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: ComplianceViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[ComplianceRunListResponse]:
    data = await _query_service(
        session,
        settings,
        user,
        metadata,
    ).history_for_file(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Compliance history retrieved successfully.",
        data=data,
        errors=None,
    )
