"""Document revision history and mutation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_revision import (
    DocumentRevisionCreate,
    DocumentRevisionListItem,
    DocumentRevisionResponse,
    DocumentRevisionSetCurrentRequest,
    DocumentRevisionSupersedeRequest,
    DocumentRevisionUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.document_revision_service import (
    DocumentRevisionService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW)),
]
RevisionManager = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_MANAGE_REVISIONS)),
]


@router.get(
    "/{document_id}/revisions",
    response_model=ApiResponse[list[DocumentRevisionListItem]],
)
async def list_document_revisions(
    document_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[list[DocumentRevisionListItem]]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).list(document_id)
    return ApiResponse(
        success=True,
        message="Document revisions retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{document_id}/revisions",
    response_model=ApiResponse[DocumentRevisionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_document_revision(
    document_id: UUID,
    payload: DocumentRevisionCreate,
    session: Session,
    user: RevisionManager,
    metadata: Metadata,
) -> ApiResponse[DocumentRevisionResponse]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).create(document_id, payload)
    return ApiResponse(
        success=True,
        message="Document revision created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/{document_id}/revisions/{revision_id}",
    response_model=ApiResponse[DocumentRevisionResponse],
)
async def get_document_revision(
    document_id: UUID,
    revision_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentRevisionResponse]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).get(document_id, revision_id)
    return ApiResponse(
        success=True,
        message="Document revision retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/{document_id}/revisions/{revision_id}",
    response_model=ApiResponse[DocumentRevisionResponse],
)
async def update_document_revision(
    document_id: UUID,
    revision_id: UUID,
    payload: DocumentRevisionUpdate,
    session: Session,
    user: RevisionManager,
    metadata: Metadata,
) -> ApiResponse[DocumentRevisionResponse]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).update(document_id, revision_id, payload)
    return ApiResponse(
        success=True,
        message="Document revision updated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{document_id}/revisions/{revision_id}/set-current",
    response_model=ApiResponse[DocumentRevisionResponse],
)
async def set_current_document_revision(
    document_id: UUID,
    revision_id: UUID,
    session: Session,
    user: RevisionManager,
    metadata: Metadata,
    payload: DocumentRevisionSetCurrentRequest | None = None,
) -> ApiResponse[DocumentRevisionResponse]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).set_current(document_id, revision_id, payload)
    return ApiResponse(
        success=True,
        message="Current document revision updated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{document_id}/revisions/{revision_id}/supersede",
    response_model=ApiResponse[DocumentRevisionResponse],
)
async def supersede_document_revision(
    document_id: UUID,
    revision_id: UUID,
    payload: DocumentRevisionSupersedeRequest,
    session: Session,
    user: RevisionManager,
    metadata: Metadata,
) -> ApiResponse[DocumentRevisionResponse]:
    data = await DocumentRevisionService(
        session, user, metadata
    ).supersede(document_id, revision_id, payload)
    return ApiResponse(
        success=True,
        message="Document revision superseded successfully.",
        data=data,
        errors=None,
    )

