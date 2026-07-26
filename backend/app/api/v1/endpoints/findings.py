"""Phase 8 finding queries, manual records, workflows, and exports."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    status,
)
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
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.finding import (
    FindingAcceptRiskRequest,
    FindingAssignRequest,
    FindingBulkActionRequest,
    FindingBulkActionResponse,
    FindingBulkAssignRequest,
    FindingCreateManualRequest,
    FindingFalsePositiveRequest,
    FindingFilter,
    FindingListResponse,
    FindingReopenRequest,
    FindingResolveRequest,
    FindingResponse,
    FindingReviewRequest,
    FindingUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.findings.finding_export_service import (
    FindingExportService,
    remove_finding_export_artifact,
)
from app.services.compliance.findings.finding_management_service import (
    FindingManagementService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
FindingViewer = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_VIEW)),
]
ManualFindingCreator = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_CREATE_MANUAL)),
]
FindingEditor = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_UPDATE)),
]
FindingReviewer = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_REVIEW)),
]
FindingResolver = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_RESOLVE)),
]
FindingReopener = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_REOPEN)),
]
FalsePositiveReviewer = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_FALSE_POSITIVE)),
]
FindingExporter = Annotated[
    User,
    Depends(require_permissions(Permission.FINDINGS_EXPORT)),
]


def _service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> FindingManagementService:
    return FindingManagementService(session, user, metadata)


def finding_filter_dependency(
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
    detected_section_id: Annotated[
        UUID | None,
        Query(alias="detectedSectionId"),
    ] = None,
    section_code: Annotated[
        str | None,
        Query(alias="section", max_length=64),
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
        datetime | None,
        Query(alias="createdFrom"),
    ] = None,
    created_to: Annotated[
        datetime | None,
        Query(alias="createdTo"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        str,
        Query(alias="sortBy", max_length=50),
    ] = "severity",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> FindingFilter:
    return FindingFilter(
        search=search,
        department_id=department_id,
        document_id=document_id,
        revision_id=revision_id,
        compliance_run_id=compliance_run_id,
        detected_section_id=detected_section_id,
        section_code=section_code,
        finding_code=finding_code,
        finding_type=finding_type,
        severity=severity,
        status=finding_status,
        language_code=language_code,
        assigned_to=assigned_to,
        created_by_system=created_by_system,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


FindingFilters = Annotated[
    FindingFilter,
    Depends(finding_filter_dependency),
]


@router.get(
    "/export",
    response_class=FileResponse,
)
async def export_findings(
    background_tasks: BackgroundTasks,
    filters: FindingFilters,
    session: Session,
    settings: Configuration,
    user: FindingExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "xlsx"],
        Query(alias="format"),
    ] = "json",
) -> FileResponse:
    artifact = await FindingExportService(
        session,
        settings,
        user,
        metadata,
    ).export(filters, export_format=export_format)
    background_tasks.add_task(
        remove_finding_export_artifact,
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
    "/manual",
    response_model=ApiResponse[FindingResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_finding(
    payload: FindingCreateManualRequest,
    session: Session,
    user: ManualFindingCreator,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).create_manual(payload)
    return ApiResponse(
        success=True,
        message="Manual compliance finding created successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/bulk-actions",
    response_model=ApiResponse[FindingBulkActionResponse],
    summary="Apply one action to multiple findings",
    description=(
        "Atomically assigns or starts review for a bounded, de-duplicated set "
        "of department-scoped findings. The entire request is rejected when "
        "any finding, transition, or assignee is invalid. Requests above the "
        "configured item limit are rejected with HTTP 422."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiResponse[None],
            "description": "The requested assignee is invalid.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ApiResponse[None],
            "description": "The caller cannot perform the selected action.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiResponse[None],
            "description": "A finding is missing or outside the caller's scope.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ApiResponse[None],
            "description": "At least one finding cannot perform the action.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ApiResponse[None],
            "description": (
                "Request validation failed or the configured bulk-action "
                "item limit was exceeded."
            ),
        },
    },
)
async def bulk_action_findings(
    payload: FindingBulkActionRequest,
    session: Session,
    settings: Configuration,
    user: FindingViewer,
    metadata: Metadata,
) -> ApiResponse[FindingBulkActionResponse]:
    service = _service(session, user, metadata)
    if isinstance(payload, FindingBulkAssignRequest):
        data = await service.bulk_assign(
            payload.finding_ids,
            assigned_to=payload.assigned_to,
            maximum_items=settings.finding_bulk_action_max_items,
        )
    else:
        data = await service.bulk_review(
            payload.finding_ids,
            comment=payload.comment,
            maximum_items=settings.finding_bulk_action_max_items,
        )
    return ApiResponse(
        success=True,
        message=f"Bulk finding {payload.action.lower()} completed successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "",
    response_model=ApiResponse[FindingListResponse],
)
async def list_findings(
    filters: FindingFilters,
    session: Session,
    user: FindingViewer,
    metadata: Metadata,
) -> ApiResponse[FindingListResponse]:
    data = await _service(session, user, metadata).list(filters)
    return ApiResponse(
        success=True,
        message="Compliance findings retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/{finding_id}",
    response_model=ApiResponse[FindingResponse],
)
async def get_finding(
    finding_id: UUID,
    session: Session,
    user: FindingViewer,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(session, user, metadata).get(finding_id)
    return ApiResponse(
        success=True,
        message="Compliance finding retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/{finding_id}",
    response_model=ApiResponse[FindingResponse],
)
async def update_finding(
    finding_id: UUID,
    payload: FindingUpdateRequest,
    session: Session,
    user: FindingEditor,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).update(finding_id, payload)
    return ApiResponse(
        success=True,
        message="Compliance finding updated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/review",
    response_model=ApiResponse[FindingResponse],
)
async def review_finding(
    finding_id: UUID,
    payload: FindingReviewRequest,
    session: Session,
    user: FindingReviewer,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).review(finding_id, comment=payload.comment)
    return ApiResponse(
        success=True,
        message="Compliance finding moved to review.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/return-to-open",
    response_model=ApiResponse[FindingResponse],
)
async def return_finding_to_open(
    finding_id: UUID,
    payload: FindingReviewRequest,
    session: Session,
    user: FindingReviewer,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).return_to_open(finding_id, comment=payload.comment)
    return ApiResponse(
        success=True,
        message="Compliance finding returned to open.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/resolve",
    response_model=ApiResponse[FindingResponse],
)
async def resolve_finding(
    finding_id: UUID,
    payload: FindingResolveRequest,
    session: Session,
    user: FindingResolver,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).resolve(finding_id, comment=payload.comment)
    return ApiResponse(
        success=True,
        message="Compliance finding resolved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/reopen",
    response_model=ApiResponse[FindingResponse],
)
async def reopen_finding(
    finding_id: UUID,
    payload: FindingReopenRequest,
    session: Session,
    user: FindingReopener,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).reopen(finding_id, reason=payload.reason)
    return ApiResponse(
        success=True,
        message="Compliance finding reopened successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/false-positive",
    response_model=ApiResponse[FindingResponse],
)
async def mark_finding_false_positive(
    finding_id: UUID,
    payload: FindingFalsePositiveRequest,
    session: Session,
    user: FalsePositiveReviewer,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).mark_false_positive(finding_id, reason=payload.reason)
    return ApiResponse(
        success=True,
        message="Compliance finding marked as false positive.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/accept-risk",
    response_model=ApiResponse[FindingResponse],
)
async def accept_finding_risk(
    finding_id: UUID,
    payload: FindingAcceptRiskRequest,
    session: Session,
    user: FindingResolver,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).accept_risk(
        finding_id,
        reason=payload.reason,
        expiry_date=payload.expiry_date,
    )
    return ApiResponse(
        success=True,
        message="Compliance finding risk accepted successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{finding_id}/assign",
    response_model=ApiResponse[FindingResponse],
)
async def assign_finding(
    finding_id: UUID,
    payload: FindingAssignRequest,
    session: Session,
    user: FindingEditor,
    metadata: Metadata,
) -> ApiResponse[FindingResponse]:
    data = await _service(
        session,
        user,
        metadata,
    ).assign(finding_id, assigned_to=payload.assigned_to)
    return ApiResponse(
        success=True,
        message="Compliance finding assigned successfully.",
        data=data,
        errors=None,
    )
