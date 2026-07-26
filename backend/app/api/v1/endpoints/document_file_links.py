"""File metadata and current downloads nested under register resources."""

from collections.abc import AsyncIterable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_file import DocumentFileListItem
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.document_file_service import DocumentFileService

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW)),
]
Downloader = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_DOWNLOAD)),
]


def _service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> DocumentFileService:
    return DocumentFileService(session, settings, user, metadata)


@router.get(
    "/{document_id}/files",
    response_model=ApiResponse[list[DocumentFileListItem]],
)
async def list_document_files(
    document_id: UUID,
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[list[DocumentFileListItem]]:
    data = await _service(
        session, settings, user, metadata
    ).list_document(document_id)
    return ApiResponse(
        success=True,
        message="Document files retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/{document_id}/revisions/{revision_id}/files",
    response_model=ApiResponse[list[DocumentFileListItem]],
)
async def list_revision_files(
    document_id: UUID,
    revision_id: UUID,
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[list[DocumentFileListItem]]:
    data = await _service(
        session, settings, user, metadata
    ).list_revision(document_id, revision_id)
    return ApiResponse(
        success=True,
        message="Revision files retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/{document_id}/revisions/{revision_id}/download")
async def download_current_revision_file(
    document_id: UUID,
    revision_id: UUID,
    session: Session,
    settings: Configuration,
    user: Downloader,
    metadata: Metadata,
) -> StreamingResponse:
    download = await _service(
        session, settings, user, metadata
    ).prepare_current_revision_download(document_id, revision_id)
    return StreamingResponse(
        cast(AsyncIterable[bytes], download.body),
        media_type=download.media_type,
        headers={
            "Content-Length": str(download.content_length),
            "Content-Disposition": download.content_disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "private, no-store",
        },
    )
