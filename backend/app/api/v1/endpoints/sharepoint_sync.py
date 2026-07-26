"""SharePoint sync profile, queue, history, item, and export endpoints."""

from __future__ import annotations

import io
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.sharepoint_enums import SharePointSyncJobStatus
from app.models.user import User
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.common import ApiResponse
from app.schemas.sharepoint_sync import (
    SharePointDeltaResetRequest,
    SharePointSyncItemListResponse,
    SharePointSyncItemResponse,
    SharePointSyncJobCreateRequest,
    SharePointSyncJobListResponse,
    SharePointSyncJobResponse,
    SharePointSyncProfileCreateRequest,
    SharePointSyncProfileListResponse,
    SharePointSyncProfileResponse,
    SharePointSyncProfileUpdateRequest,
    SharePointSyncRunRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint.sync_job_service import (
    SharePointSyncJobService,
)

router = APIRouter(prefix="/sharepoint", tags=["SharePoint Synchronisation"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
SyncViewer = Annotated[
    User, Depends(require_permissions("sharepoint:view_history"))
]
SyncConfigurator = Annotated[
    User, Depends(require_permissions("sharepoint:configure"))
]
SyncRunner = Annotated[
    User, Depends(require_permissions("sharepoint:sync"))
]
SyncCanceller = Annotated[
    User, Depends(require_permissions("sharepoint:cancel_sync"))
]


@router.get(
    "/sync-profiles",
    response_model=ApiResponse[SharePointSyncProfileListResponse],
)
async def list_sharepoint_sync_profiles(
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
    include_inactive: Annotated[
        bool, Query(alias="includeInactive")
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointSyncProfileListResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).list_profiles(
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint sync profiles retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-profiles",
    response_model=ApiResponse[SharePointSyncProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sharepoint_sync_profile(
    payload: SharePointSyncProfileCreateRequest,
    session: Session,
    settings: Configuration,
    user: SyncConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncProfileResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).create_profile(payload)
    return ApiResponse(
        success=True,
        message="SharePoint sync profile created successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/sync-profiles/{profile_id}",
    response_model=ApiResponse[SharePointSyncProfileResponse],
)
async def get_sharepoint_sync_profile(
    profile_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncProfileResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).get_profile(profile_id)
    return ApiResponse(
        success=True,
        message="SharePoint sync profile retrieved successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/sync-profiles/{profile_id}",
    response_model=ApiResponse[SharePointSyncProfileResponse],
)
async def update_sharepoint_sync_profile(
    profile_id: UUID,
    payload: SharePointSyncProfileUpdateRequest,
    session: Session,
    settings: Configuration,
    user: SyncConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncProfileResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).update_profile(profile_id, payload)
    return ApiResponse(
        success=True,
        message="SharePoint sync profile updated successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-profiles/{profile_id}/activate",
    response_model=ApiResponse[SharePointSyncProfileResponse],
)
async def activate_sharepoint_sync_profile(
    profile_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncProfileResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).set_profile_active(profile_id, active=True)
    return ApiResponse(
        success=True,
        message="SharePoint sync profile activated.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-profiles/{profile_id}/deactivate",
    response_model=ApiResponse[SharePointSyncProfileResponse],
)
async def deactivate_sharepoint_sync_profile(
    profile_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncProfileResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).set_profile_active(profile_id, active=False)
    return ApiResponse(
        success=True,
        message="SharePoint sync profile deactivated.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-profiles/{profile_id}/run",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_sharepoint_sync_profile(
    profile_id: UUID,
    payload: SharePointSyncRunRequest,
    session: Session,
    settings: Configuration,
    user: SyncRunner,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).queue_job(
        SharePointSyncJobCreateRequest(
            sync_profile_id=profile_id,
            job_type=payload.job_type,
            scope=payload.scope,
        )
    )
    return ApiResponse(
        success=True,
        message="SharePoint sync job queued.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-profiles/{profile_id}/reset-delta",
    response_model=ApiResponse[dict[str, bool]],
)
async def reset_sharepoint_delta(
    profile_id: UUID,
    payload: SharePointDeltaResetRequest,
    session: Session,
    settings: Configuration,
    user: SyncConfigurator,
    metadata: Metadata,
) -> ApiResponse[dict[str, bool]]:
    reset = await SharePointSyncJobService(
        session, settings, user, metadata
    ).reset_delta(
        profile_id,
        reason=payload.confirmation_reason,
    )
    return ApiResponse(
        success=True,
        message="SharePoint delta state reset completed.",
        data={"reset": reset},
        errors=None,
    )


@router.get(
    "/sync-jobs",
    response_model=ApiResponse[SharePointSyncJobListResponse],
)
async def list_sharepoint_sync_jobs(
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
    statuses: Annotated[
        list[SharePointSyncJobStatus] | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointSyncJobListResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).list_jobs(
        statuses=statuses,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint sync jobs retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-jobs",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_sharepoint_sync_job(
    payload: SharePointSyncJobCreateRequest,
    session: Session,
    settings: Configuration,
    user: SyncRunner,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).queue_job(payload)
    return ApiResponse(
        success=True,
        message="SharePoint sync job queued.",
        data=result,
        errors=None,
    )


@router.get(
    "/sync-jobs/{job_id}",
    response_model=ApiResponse[SharePointSyncJobResponse],
)
async def get_sharepoint_sync_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).get_job(job_id)
    return ApiResponse(
        success=True,
        message="SharePoint sync job retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-jobs/{job_id}/cancel",
    response_model=ApiResponse[SharePointSyncJobResponse],
)
async def cancel_sharepoint_sync_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncCanceller,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="SharePoint sync cancellation requested.",
        data=result,
        errors=None,
    )


@router.post(
    "/sync-jobs/{job_id}/retry",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_sharepoint_sync_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncRunner,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointSyncJobService(
        session, settings, user, metadata
    ).retry(job_id)
    return ApiResponse(
        success=True,
        message="SharePoint sync job queued for retry.",
        data=result,
        errors=None,
    )


@router.get(
    "/sync-jobs/{job_id}/items",
    response_model=ApiResponse[SharePointSyncItemListResponse],
)
async def list_sharepoint_sync_items(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointSyncItemListResponse]:
    service = SharePointSyncJobService(
        session, settings, user, metadata
    )
    await service.get_job(job_id)
    items, total = await SharePointSyncRepository(session).list_items(
        job_id,
        page=page,
        page_size=page_size,
    )
    result = SharePointSyncItemListResponse(
        items=[
            SharePointSyncItemResponse.model_validate(item)
            for item in items
        ],
        page=page,
        pageSize=page_size,
        totalItems=total,
        totalPages=(total + page_size - 1) // page_size if total else 0,
    )
    return ApiResponse(
        success=True,
        message="SharePoint sync items retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get("/sync-jobs/{job_id}/export")
async def export_sharepoint_sync_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SyncViewer,
    metadata: Metadata,
    output_format: Annotated[
        Literal["json", "xlsx"], Query(alias="format")
    ] = "json",
) -> StreamingResponse:
    service = SharePointSyncJobService(
        session, settings, user, metadata
    )
    job = await service.get_job(job_id)
    items, total = await SharePointSyncRepository(session).list_items(
        job_id,
        page=1,
        page_size=100_000,
    )
    rows = [
        SharePointSyncItemResponse.model_validate(item).model_dump(
            mode="json",
            by_alias=True,
        )
        for item in items
    ]
    if output_format == "json":
        body = io.BytesIO(
            json.dumps(
                {
                    "job": job.model_dump(mode="json", by_alias=True),
                    "items": rows,
                    "totalItems": total,
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
        )
        media_type = "application/json"
    else:
        body = _xlsx_export(rows)
        media_type = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    filename = f"sharepoint-sync-{job_id}.{output_format}"
    return StreamingResponse(
        body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _xlsx_export(rows: list[dict[str, object]]) -> io.BytesIO:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Sync Items")
    headers = [
        "id",
        "operation",
        "status",
        "documentFileId",
        "remoteItemId",
        "remotePath",
        "remoteEtagAfter",
        "errorCode",
        "errorMessage",
        "createdAt",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append(
            [
                (
                    json.dumps(row.get(header), ensure_ascii=False)
                    if isinstance(row.get(header), (dict, list))
                    else row.get(header)
                )
                for header in headers
            ]
        )
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
