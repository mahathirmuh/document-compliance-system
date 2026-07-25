"""Master-data XLSX template, preview, confirm, and export endpoints."""

from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.authorization import has_permission
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationError
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_type import DocumentTypeCategory
from app.schemas.master_data import (
    ImportConfirmResponse,
    ImportEntityType,
    ImportMode,
    ImportPreviewResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.import_export_service import (
    XLSX_CONTENT_TYPE,
    MasterDataImportExportService,
)

from fastapi import APIRouter

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_VIEW)),
]
Creator = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_CREATE)),
]


def _service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> MasterDataImportExportService:
    return MasterDataImportExportService(session, settings, user, metadata)


@router.get("/import/template/{entity_type}")
async def download_import_template(
    entity_type: ImportEntityType,
    session: Session,
    settings: AppSettings,
    user: Viewer,
    metadata: Metadata,
) -> StreamingResponse:
    content, filename = _service(
        session, settings, user, metadata
    ).template(entity_type)
    return StreamingResponse(
        BytesIO(content),
        media_type=XLSX_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post(
    "/import/preview",
    response_model=ApiResponse[ImportPreviewResponse],
)
async def preview_import(
    entity_type: Annotated[ImportEntityType, Form(alias="entityType")],
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: AppSettings,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[ImportPreviewResponse]:
    content = await file.read()
    await file.close()
    data = await _service(session, settings, user, metadata).preview(
        entity_type,
        filename=file.filename,
        content=content,
    )
    return ApiResponse(
        success=True,
        message="Import preview generated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/import/confirm",
    response_model=ApiResponse[ImportConfirmResponse],
)
async def confirm_import(
    entity_type: Annotated[ImportEntityType, Form(alias="entityType")],
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: AppSettings,
    user: Creator,
    metadata: Metadata,
    mode: Annotated[ImportMode, Form()] = ImportMode.CREATE_ONLY,
) -> ApiResponse[ImportConfirmResponse]:
    if (
        mode is ImportMode.UPSERT
        and not has_permission(
            user.role,
            Permission.MASTER_DATA_UPDATE,
            is_superuser=user.is_superuser,
        )
    ):
        raise AuthorizationError(
            "UPSERT import requires master_data:update permission."
        )
    content = await file.read()
    await file.close()
    data = await _service(session, settings, user, metadata).confirm(
        entity_type,
        mode=mode,
        filename=file.filename,
        content=content,
    )
    return ApiResponse(
        success=True,
        message="Master data imported successfully.",
        data=data,
        errors=None,
    )


@router.get("/export/{entity_type}")
async def export_master_data(
    entity_type: ImportEntityType,
    session: Session,
    settings: AppSettings,
    user: Viewer,
    metadata: Metadata,
    search: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    category: DocumentTypeCategory | None = None,
) -> StreamingResponse:
    content, filename = await _service(
        session,
        settings,
        user,
        metadata,
    ).export(
        entity_type,
        search=search,
        is_active=is_active,
        department_id=department_id,
        document_type_id=document_type_id,
        category=category.value if category is not None else None,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=XLSX_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
