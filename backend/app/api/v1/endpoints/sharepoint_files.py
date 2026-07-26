"""Authenticated SharePoint actions for internal document files."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.sharepoint_sync import (
    SharePointFileStatusResponse,
    SharePointFileVersionListResponse,
    SharePointSyncJobResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint.file_integration_service import (
    SharePointFileIntegrationService,
)

router = APIRouter(tags=["SharePoint Document Files"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
FileViewer = Annotated[
    User, Depends(require_permissions("sharepoint:view"))
]
FilePusher = Annotated[
    User, Depends(require_permissions("sharepoint:push"))
]
FilePuller = Annotated[
    User, Depends(require_permissions("sharepoint:pull"))
]
FileSyncer = Annotated[
    User, Depends(require_permissions("sharepoint:sync"))
]


@router.post(
    "/document-files/{file_id}/sharepoint/push",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def push_document_file_to_sharepoint(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FilePusher,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).push(file_id)
    return ApiResponse(
        success=True,
        message="SharePoint push job queued.",
        data=result,
        errors=None,
    )


@router.post(
    "/document-files/{file_id}/sharepoint/pull",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def pull_document_file_from_sharepoint(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FilePuller,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).pull(file_id)
    return ApiResponse(
        success=True,
        message="SharePoint pull job queued.",
        data=result,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/sharepoint/status",
    response_model=ApiResponse[SharePointFileStatusResponse],
)
async def get_document_file_sharepoint_status(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FileViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointFileStatusResponse]:
    result = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).status(file_id)
    return ApiResponse(
        success=True,
        message="SharePoint file status retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/sharepoint/versions",
    response_model=ApiResponse[SharePointFileVersionListResponse],
)
async def list_document_file_sharepoint_versions(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FileViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointFileVersionListResponse]:
    result = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).list_versions(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="SharePoint file versions retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/document-files/{file_id}/sharepoint/reconcile",
    response_model=ApiResponse[SharePointSyncJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def reconcile_document_file_sharepoint(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FileSyncer,
    metadata: Metadata,
) -> ApiResponse[SharePointSyncJobResponse]:
    result = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).reconcile(file_id)
    return ApiResponse(
        success=True,
        message="SharePoint reconciliation job queued.",
        data=result,
        errors=None,
    )


@router.get("/sharepoint/files/{file_id}/download")
async def download_sharepoint_document_file(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FileViewer,
    metadata: Metadata,
) -> StreamingResponse:
    download = await SharePointFileIntegrationService(
        session, settings, user, metadata
    ).prepare_download(file_id)
    headers = {
        "Content-Disposition": download.content_disposition,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if download.content_length is not None:
        headers["Content-Length"] = str(download.content_length)
    return StreamingResponse(
        download.body,
        media_type=download.media_type,
        headers=headers,
    )
