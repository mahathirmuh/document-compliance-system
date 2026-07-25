"""Document Register XLSX template, preview, and confirmation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse, ErrorDetail
from app.schemas.document_import import (
    DocumentImportMode,
    DocumentImportPreviewResponse,
    DocumentImportResultResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.document_import_service import (
    XLSX_CONTENT_TYPE,
    DocumentImportService,
)

router = APIRouter()

UPLOAD_READ_CHUNK_SIZE = 1024 * 1024

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Importer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_IMPORT)),
]


async def _read_bounded_upload(
    file: UploadFile,
    settings: Settings,
) -> bytes:
    """Stop reading once the configured byte limit has been exceeded."""
    maximum = settings.document_import_max_file_size_mb * 1024 * 1024
    content = bytearray()
    while len(content) <= maximum:
        chunk = await file.read(
            min(UPLOAD_READ_CHUNK_SIZE, maximum + 1 - len(content))
        )
        if not chunk:
            return bytes(content)
        content.extend(chunk)
    raise ApplicationError(
        "Document Register import failed.",
        status_code=400,
        errors=[
            ErrorDetail(
                field="file",
                message=(
                    "File exceeds the configured maximum size of "
                    f"{settings.document_import_max_file_size_mb} MB."
                ),
            )
        ],
    )


@router.get("/import/template")
async def download_document_import_template(
    session: Session,
    settings: Configuration,
    user: Importer,
    metadata: Metadata,
) -> Response:
    content, filename = await DocumentImportService(
        session, settings, user, metadata
    ).template()
    return Response(
        content=content,
        media_type=XLSX_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post(
    "/import/preview",
    response_model=ApiResponse[DocumentImportPreviewResponse],
)
async def preview_document_import(
    session: Session,
    settings: Configuration,
    user: Importer,
    metadata: Metadata,
    file: Annotated[UploadFile, File()],
) -> ApiResponse[DocumentImportPreviewResponse]:
    content = await _read_bounded_upload(file, settings)
    data = await DocumentImportService(
        session, settings, user, metadata
    ).preview(filename=file.filename, content=content)
    return ApiResponse(
        success=True,
        message="Document Register import preview completed.",
        data=data,
        errors=None,
    )


@router.post(
    "/import/confirm",
    response_model=ApiResponse[DocumentImportResultResponse],
)
async def confirm_document_import(
    session: Session,
    settings: Configuration,
    user: Importer,
    metadata: Metadata,
    file: Annotated[UploadFile, File()],
    mode: Annotated[
        DocumentImportMode,
        Form(),
    ] = DocumentImportMode.CREATE_AND_ADD_REVISION,
) -> ApiResponse[DocumentImportResultResponse]:
    content = await _read_bounded_upload(file, settings)
    data = await DocumentImportService(
        session, settings, user, metadata
    ).confirm(
        mode=mode,
        filename=file.filename,
        content=content,
    )
    return ApiResponse(
        success=True,
        message="Document Register import completed.",
        data=data,
        errors=None,
    )
