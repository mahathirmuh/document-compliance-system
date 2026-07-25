"""Physical document upload, history, and secure file endpoints."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.document_file import DocumentFileStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_file import (
    DocumentFileDeleteRequest,
    DocumentFileDetailResponse,
    DocumentFileListResponse,
    DocumentFileRestoreRequest,
)
from app.schemas.document_upload import (
    BatchUploadConfirmationRequest,
    BatchUploadResult,
    UploadConfirmationRequest,
    UploadConfirmationResult,
)
from app.schemas.upload_session import (
    BatchUploadResponse,
    UploadSessionResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.batch_upload_service import BatchUploadService
from app.services.documents.document_file_service import DocumentFileService
from app.services.documents.document_upload_service import (
    DocumentUploadService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Uploader = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_UPLOAD)),
]
BatchUploader = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_BATCH_UPLOAD)),
]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW)),
]
Downloader = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_DOWNLOAD)),
]
Replacer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_REPLACE_FILE)),
]
FileDeleter = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_DELETE_FILE)),
]
HistoryViewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW_FILE_HISTORY)),
]


def _upload_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> DocumentUploadService:
    return DocumentUploadService(session, settings, user, metadata)


def _file_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> DocumentFileService:
    return DocumentFileService(session, settings, user, metadata)


@router.post(
    "/upload",
    response_model=ApiResponse[UploadSessionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_and_identify(
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: Configuration,
    user: Uploader,
    metadata: Metadata,
    document_id: Annotated[
        UUID | None,
        Form(alias="documentId"),
    ] = None,
    revision_id: Annotated[
        UUID | None,
        Form(alias="revisionId"),
    ] = None,
) -> ApiResponse[UploadSessionResponse]:
    data = await _upload_service(
        session, settings, user, metadata
    ).preview_single(
        file,
        document_id=document_id,
        revision_id=revision_id,
    )
    return ApiResponse(
        success=True,
        message="Document uploaded and identified successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/upload/{session_id}/confirm",
    response_model=ApiResponse[UploadConfirmationResult],
)
async def confirm_upload(
    session_id: UUID,
    payload: UploadConfirmationRequest,
    session: Session,
    settings: Configuration,
    user: Uploader,
    metadata: Metadata,
) -> ApiResponse[UploadConfirmationResult]:
    data = await _upload_service(
        session, settings, user, metadata
    ).confirm(session_id, payload)
    return ApiResponse(
        success=True,
        message="Document file upload confirmed successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/upload/{session_id}/cancel",
    response_model=ApiResponse[UploadSessionResponse],
)
async def cancel_upload(
    session_id: UUID,
    session: Session,
    settings: Configuration,
    user: Uploader,
    metadata: Metadata,
) -> ApiResponse[UploadSessionResponse]:
    data = await _upload_service(
        session, settings, user, metadata
    ).cancel(session_id)
    return ApiResponse(
        success=True,
        message="Upload session cancelled successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/batch-upload",
    response_model=ApiResponse[BatchUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def batch_upload_and_identify(
    files: Annotated[list[UploadFile], File()],
    session: Session,
    settings: Configuration,
    user: BatchUploader,
    metadata: Metadata,
) -> ApiResponse[BatchUploadResponse]:
    data = await BatchUploadService(
        session, settings, user, metadata
    ).preview(files)
    return ApiResponse(
        success=True,
        message="Batch uploaded and identified successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/batch-upload/{session_id}/confirm",
    response_model=ApiResponse[BatchUploadResult],
)
async def confirm_batch_upload(
    session_id: UUID,
    payload: BatchUploadConfirmationRequest,
    session: Session,
    settings: Configuration,
    user: BatchUploader,
    metadata: Metadata,
) -> ApiResponse[BatchUploadResult]:
    data = await BatchUploadService(
        session, settings, user, metadata
    ).confirm_preview(session_id, payload)
    return ApiResponse(
        success=True,
        message="Batch upload confirmation completed.",
        data=data,
        errors=None,
    )


# Static history route must precede /{file_id}.
@router.get(
    "/history",
    response_model=ApiResponse[DocumentFileListResponse],
)
async def file_history(
    session: Session,
    settings: Configuration,
    user: HistoryViewer,
    metadata: Metadata,
    document_id: Annotated[
        UUID | None,
        Query(alias="documentId"),
    ] = None,
    revision_id: Annotated[
        UUID | None,
        Query(alias="revisionId"),
    ] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    uploaded_by: Annotated[
        UUID | None,
        Query(alias="uploadedBy"),
    ] = None,
    file_status: Annotated[
        DocumentFileStatus | None,
        Query(alias="fileStatus"),
    ] = None,
    file_extension: Annotated[
        Literal["pdf", "docx", "xlsx"] | None,
        Query(alias="fileExtension"),
    ] = None,
    uploaded_from: Annotated[
        date | None,
        Query(alias="uploadedFrom"),
    ] = None,
    uploaded_to: Annotated[
        date | None,
        Query(alias="uploadedTo"),
    ] = None,
    search: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[DocumentFileListResponse]:
    data = await _file_service(
        session, settings, user, metadata
    ).history(
        document_id=document_id,
        revision_id=revision_id,
        department_id=department_id,
        uploaded_by=uploaded_by,
        file_status=file_status,
        file_extension=file_extension,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Document file history retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/{file_id}",
    response_model=ApiResponse[DocumentFileDetailResponse],
)
async def get_document_file(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentFileDetailResponse]:
    data = await _file_service(
        session, settings, user, metadata
    ).get(file_id)
    return ApiResponse(
        success=True,
        message="Document file metadata retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/{file_id}/download")
async def download_document_file(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: Downloader,
    metadata: Metadata,
) -> StreamingResponse:
    download = await _file_service(
        session, settings, user, metadata
    ).prepare_download(file_id)
    return StreamingResponse(
        download.body,
        media_type=download.media_type,
        headers={
            "Content-Length": str(download.content_length),
            "Content-Disposition": download.content_disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/{file_id}/replace",
    response_model=ApiResponse[DocumentFileDetailResponse],
)
async def replace_document_file(
    file_id: UUID,
    file: Annotated[UploadFile, File()],
    reason: Annotated[str, Form(min_length=1, max_length=1000)],
    session: Session,
    settings: Configuration,
    user: Replacer,
    metadata: Metadata,
) -> ApiResponse[DocumentFileDetailResponse]:
    data = await _file_service(
        session, settings, user, metadata
    ).replace(file_id, file, reason)
    return ApiResponse(
        success=True,
        message="Document file replaced successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{file_id}/delete",
    response_model=ApiResponse[DocumentFileDetailResponse],
)
async def delete_document_file(
    file_id: UUID,
    payload: DocumentFileDeleteRequest,
    session: Session,
    settings: Configuration,
    user: FileDeleter,
    metadata: Metadata,
) -> ApiResponse[DocumentFileDetailResponse]:
    data = await _file_service(
        session, settings, user, metadata
    ).delete(file_id, payload)
    return ApiResponse(
        success=True,
        message="Document file deleted successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{file_id}/restore",
    response_model=ApiResponse[DocumentFileDetailResponse],
)
async def restore_document_file(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: FileDeleter,
    metadata: Metadata,
    payload: DocumentFileRestoreRequest | None = None,
) -> ApiResponse[DocumentFileDetailResponse]:
    data = await _file_service(
        session, settings, user, metadata
    ).restore(file_id, payload or DocumentFileRestoreRequest())
    return ApiResponse(
        success=True,
        message="Document file restored successfully.",
        data=data,
        errors=None,
    )
