"""Authenticated SharePoint connection, browser, and mapping endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.integrations.microsoft_graph.sharepoint.sharepoint_drive_service import (
    SharePointDriveService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_folder_service import (
    SharePointFolderService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_site_service import (
    SharePointSiteService,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.sharepoint import (
    SharePointConnectionCreateRequest,
    SharePointConnectionListResponse,
    SharePointConnectionResponse,
    SharePointConnectionTestResponse,
    SharePointConnectionUpdateRequest,
    SharePointDriveResponse,
    SharePointFolderCreateRequest,
    SharePointFolderMappingCreateRequest,
    SharePointFolderMappingListResponse,
    SharePointFolderMappingResponse,
    SharePointFolderMappingUpdateRequest,
    SharePointFolderResponse,
    SharePointMetadataMappingCreateRequest,
    SharePointMetadataMappingListResponse,
    SharePointMetadataMappingResponse,
    SharePointMetadataMappingUpdateRequest,
    SharePointSiteResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint.connection_service import (
    SharePointConnectionService,
)
from app.services.sharepoint.graph_factory import create_graph_client
from app.services.sharepoint.mapping_service import SharePointMappingService

router = APIRouter(
    prefix="/integrations/sharepoint",
    tags=["SharePoint Integration"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
SharePointViewer = Annotated[
    User, Depends(require_permissions("sharepoint:view"))
]
SharePointConfigurator = Annotated[
    User, Depends(require_permissions("sharepoint:configure"))
]
SharePointTester = Annotated[
    User, Depends(require_permissions("sharepoint:test_connection"))
]


@router.get(
    "/connections",
    response_model=ApiResponse[SharePointConnectionListResponse],
)
async def list_sharepoint_connections(
    session: Session,
    settings: Configuration,
    user: SharePointViewer,
    metadata: Metadata,
    include_inactive: Annotated[
        bool, Query(alias="includeInactive")
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointConnectionListResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).list(
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint connections retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/connections",
    response_model=ApiResponse[SharePointConnectionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sharepoint_connection(
    payload: SharePointConnectionCreateRequest,
    session: Session,
    settings: Configuration,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointConnectionResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).create(payload)
    return ApiResponse(
        success=True,
        message="SharePoint connection created successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/connections/{connection_id}",
    response_model=ApiResponse[SharePointConnectionResponse],
)
async def get_sharepoint_connection(
    connection_id: UUID,
    session: Session,
    settings: Configuration,
    user: SharePointViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointConnectionResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).get(connection_id)
    return ApiResponse(
        success=True,
        message="SharePoint connection retrieved successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/connections/{connection_id}",
    response_model=ApiResponse[SharePointConnectionResponse],
)
async def update_sharepoint_connection(
    connection_id: UUID,
    payload: SharePointConnectionUpdateRequest,
    session: Session,
    settings: Configuration,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointConnectionResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).update(connection_id, payload)
    return ApiResponse(
        success=True,
        message="SharePoint connection updated successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/connections/{connection_id}/test",
    response_model=ApiResponse[SharePointConnectionTestResponse],
)
async def test_sharepoint_connection(
    connection_id: UUID,
    session: Session,
    settings: Configuration,
    user: SharePointTester,
    metadata: Metadata,
) -> ApiResponse[SharePointConnectionTestResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).test(connection_id)
    return ApiResponse(
        success=True,
        message="SharePoint connection test completed.",
        data=result,
        errors=None,
    )


@router.post(
    "/connections/{connection_id}/disable",
    response_model=ApiResponse[SharePointConnectionResponse],
)
async def disable_sharepoint_connection(
    connection_id: UUID,
    session: Session,
    settings: Configuration,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointConnectionResponse]:
    result = await SharePointConnectionService(
        session, settings, user, metadata
    ).disable(connection_id)
    return ApiResponse(
        success=True,
        message="SharePoint connection disabled successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/sites/resolve",
    response_model=ApiResponse[SharePointSiteResponse],
)
async def resolve_sharepoint_site(
    connection_id: Annotated[UUID, Query(alias="connectionId")],
    session: Session,
    settings: Configuration,
    user: SharePointViewer,
    metadata: Metadata,
) -> ApiResponse[SharePointSiteResponse]:
    connection = await SharePointConnectionService(
        session, settings, user, metadata
    ).get(connection_id)
    graph = create_graph_client(settings)
    try:
        site = await SharePointSiteService(graph).resolve_site(
            hostname=connection.site_hostname,
            site_path=connection.site_path,
        )
    finally:
        await graph.close()
    result = SharePointSiteResponse(
        id=str(site["id"]),
        display_name=_optional_string(site.get("displayName")),
        name=_optional_string(site.get("name")),
        web_url=_optional_string(site.get("webUrl")),
    )
    return ApiResponse(
        success=True,
        message="SharePoint site resolved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/drives",
    response_model=ApiResponse[list[SharePointDriveResponse]],
)
async def list_sharepoint_drives(
    connection_id: Annotated[UUID, Query(alias="connectionId")],
    session: Session,
    settings: Configuration,
    user: SharePointViewer,
    metadata: Metadata,
) -> ApiResponse[list[SharePointDriveResponse]]:
    connection = await SharePointConnectionService(
        session, settings, user, metadata
    ).get(connection_id)
    graph = create_graph_client(settings)
    try:
        site_id = connection.site_id
        if not site_id:
            site = await SharePointSiteService(graph).resolve_site(
                hostname=connection.site_hostname,
                site_path=connection.site_path,
            )
            site_id = str(site["id"])
        drives = await SharePointDriveService(graph).list_drives(site_id)
    finally:
        await graph.close()
    result = [
        SharePointDriveResponse(
            id=str(item["id"]),
            name=str(item.get("name") or ""),
            drive_type=_optional_string(item.get("driveType")),
            web_url=_optional_string(item.get("webUrl")),
        )
        for item in drives
        if item.get("id")
    ]
    return ApiResponse(
        success=True,
        message="SharePoint drives retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/folders",
    response_model=ApiResponse[list[SharePointFolderResponse]],
)
async def list_sharepoint_folders(
    connection_id: Annotated[UUID, Query(alias="connectionId")],
    session: Session,
    settings: Configuration,
    user: SharePointViewer,
    metadata: Metadata,
    parent_item_id: Annotated[
        str | None, Query(alias="parentItemId", max_length=1000)
    ] = None,
    folder_path: Annotated[
        str | None, Query(alias="folderPath", max_length=1000)
    ] = None,
) -> ApiResponse[list[SharePointFolderResponse]]:
    connection = await SharePointConnectionService(
        session, settings, user, metadata
    ).get(connection_id)
    if not connection.drive_id:
        raise ValueError("SharePoint connection has no resolved drive.")
    graph = create_graph_client(settings)
    try:
        items = await SharePointFolderService(graph).list_children(
            drive_id=connection.drive_id,
            folder_id=parent_item_id,
            folder_path=folder_path or connection.root_folder_path,
        )
    finally:
        await graph.close()
    result = [
        _folder_response(item)
        for item in items
        if isinstance(item.get("folder"), dict)
    ]
    return ApiResponse(
        success=True,
        message="SharePoint folders retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/folders",
    response_model=ApiResponse[SharePointFolderResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sharepoint_folder(
    payload: SharePointFolderCreateRequest,
    session: Session,
    settings: Configuration,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointFolderResponse]:
    connection = await SharePointConnectionService(
        session, settings, user, metadata
    ).get(payload.connection_id)
    if not connection.drive_id:
        raise ValueError("SharePoint connection has no resolved drive.")
    graph = create_graph_client(settings)
    try:
        item = await SharePointFolderService(graph).create_folder(
            drive_id=connection.drive_id,
            name=payload.name,
            parent_item_id=payload.parent_item_id,
        )
    finally:
        await graph.close()
    return ApiResponse(
        success=True,
        message="SharePoint folder created successfully.",
        data=_folder_response(item),
        errors=None,
    )


@router.get(
    "/folder-mappings",
    response_model=ApiResponse[SharePointFolderMappingListResponse],
)
async def list_sharepoint_folder_mappings(
    session: Session,
    user: SharePointViewer,
    metadata: Metadata,
    connection_id: Annotated[
        UUID | None, Query(alias="connectionId")
    ] = None,
    include_inactive: Annotated[
        bool, Query(alias="includeInactive")
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointFolderMappingListResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).list_folders(
        connection_id=connection_id,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint folder mappings retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/folder-mappings",
    response_model=ApiResponse[SharePointFolderMappingResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sharepoint_folder_mapping(
    payload: SharePointFolderMappingCreateRequest,
    session: Session,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointFolderMappingResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).create_folder(payload)
    return ApiResponse(
        success=True,
        message="SharePoint folder mapping created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/folder-mappings/{mapping_id}",
    response_model=ApiResponse[SharePointFolderMappingResponse],
)
async def update_sharepoint_folder_mapping(
    mapping_id: UUID,
    payload: SharePointFolderMappingUpdateRequest,
    session: Session,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointFolderMappingResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).update_folder(mapping_id, payload)
    return ApiResponse(
        success=True,
        message="SharePoint folder mapping updated successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/metadata-mappings",
    response_model=ApiResponse[SharePointMetadataMappingListResponse],
)
async def list_sharepoint_metadata_mappings(
    session: Session,
    user: SharePointViewer,
    metadata: Metadata,
    connection_id: Annotated[
        UUID | None, Query(alias="connectionId")
    ] = None,
    include_inactive: Annotated[
        bool, Query(alias="includeInactive")
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[SharePointMetadataMappingListResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).list_metadata(
        connection_id=connection_id,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="SharePoint metadata mappings retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/metadata-mappings",
    response_model=ApiResponse[SharePointMetadataMappingResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sharepoint_metadata_mapping(
    payload: SharePointMetadataMappingCreateRequest,
    session: Session,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointMetadataMappingResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).create_metadata(payload)
    return ApiResponse(
        success=True,
        message="SharePoint metadata mapping created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/metadata-mappings/{mapping_id}",
    response_model=ApiResponse[SharePointMetadataMappingResponse],
)
async def update_sharepoint_metadata_mapping(
    mapping_id: UUID,
    payload: SharePointMetadataMappingUpdateRequest,
    session: Session,
    user: SharePointConfigurator,
    metadata: Metadata,
) -> ApiResponse[SharePointMetadataMappingResponse]:
    result = await SharePointMappingService(
        session, user, metadata
    ).update_metadata(mapping_id, payload)
    return ApiResponse(
        success=True,
        message="SharePoint metadata mapping updated successfully.",
        data=result,
        errors=None,
    )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


def _folder_response(item: dict[str, Any]) -> SharePointFolderResponse:
    folder = item.get("folder")
    child_count_value = (
        folder.get("childCount") if isinstance(folder, dict) else None
    )
    return SharePointFolderResponse(
        id=str(item["id"]),
        name=str(item.get("name") or ""),
        web_url=_optional_string(item.get("webUrl")),
        parent_reference=(
            item.get("parentReference")
            if isinstance(item.get("parentReference"), dict)
            else None
        ),
        child_count=(
            int(child_count_value)
            if isinstance(child_count_value, (int, str))
            else None
        ),
    )
