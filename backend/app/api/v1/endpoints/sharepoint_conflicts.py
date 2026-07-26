"""Department-scoped SharePoint conflict review endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.database.session import get_db_session
from app.models.sharepoint_enums import SyncConflictStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.sharepoint_sync import (
    SharePointConflictAssignRequest,
    SharePointConflictIgnoreRequest,
    SharePointConflictListResponse,
    SharePointConflictResolveRequest,
    SharePointConflictResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint.conflict_service import (
    SharePointConflictService,
)

router = APIRouter(
    prefix="/sharepoint/conflicts",
    tags=["SharePoint Conflicts"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ConflictViewer = Annotated[
    User, Depends(require_permissions("sharepoint:view_conflicts"))
]
ConflictResolver = Annotated[
    User, Depends(require_permissions("sharepoint:resolve_conflicts"))
]


@router.get(
    "",
    response_model=ApiResponse[SharePointConflictListResponse],
)
async def list_sharepoint_conflicts(
    session: Session,
    user: ConflictViewer,
    metadata: Metadata,
    statuses: Annotated[
        list[SyncConflictStatus] | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointConflictListResponse]:
    result = await SharePointConflictService(
        session, user, metadata
    ).list(
        statuses=statuses,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint conflicts retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/{conflict_id}",
    response_model=ApiResponse[SharePointConflictResponse],
)
async def get_sharepoint_conflict(
    conflict_id: UUID,
    session: Session,
    user: ConflictViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointConflictResponse]:
    result = await SharePointConflictService(
        session, user, metadata
    ).get(conflict_id)
    return ApiResponse(
        success=True,
        message="SharePoint conflict retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/{conflict_id}/assign",
    response_model=ApiResponse[SharePointConflictResponse],
)
async def assign_sharepoint_conflict(
    conflict_id: UUID,
    payload: SharePointConflictAssignRequest,
    session: Session,
    user: ConflictResolver,
    metadata: Metadata,
) -> ApiResponse[SharePointConflictResponse]:
    result = await SharePointConflictService(
        session, user, metadata
    ).assign(conflict_id, assigned_to=payload.assigned_to)
    return ApiResponse(
        success=True,
        message="SharePoint conflict assigned successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/{conflict_id}/resolve",
    response_model=ApiResponse[SharePointConflictResponse],
)
async def resolve_sharepoint_conflict(
    conflict_id: UUID,
    payload: SharePointConflictResolveRequest,
    session: Session,
    user: ConflictResolver,
    metadata: Metadata,
) -> ApiResponse[SharePointConflictResponse]:
    result = await SharePointConflictService(
        session, user, metadata
    ).resolve(
        conflict_id,
        resolution=payload.resolution,
        comment=payload.comment,
    )
    return ApiResponse(
        success=True,
        message="SharePoint conflict resolved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/{conflict_id}/ignore",
    response_model=ApiResponse[SharePointConflictResponse],
)
async def ignore_sharepoint_conflict(
    conflict_id: UUID,
    payload: SharePointConflictIgnoreRequest,
    session: Session,
    user: ConflictResolver,
    metadata: Metadata,
) -> ApiResponse[SharePointConflictResponse]:
    result = await SharePointConflictService(
        session, user, metadata
    ).ignore(conflict_id, comment=payload.comment)
    return ApiResponse(
        success=True,
        message="SharePoint conflict ignored.",
        data=result,
        errors=None,
    )
