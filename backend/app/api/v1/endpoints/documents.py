"""Document Register list, CRUD, parsing, archive, restore, and bulk API."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
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
from app.schemas.document import (
    BulkArchiveRequest,
    BulkDocumentResult,
    BulkRestoreRequest,
    BulkUpdateStatusRequest,
    DocumentArchiveRequest,
    DocumentCreate,
    DocumentDetailResponse,
    DocumentFilter,
    DocumentFormOptionsResponse,
    DocumentListResponse,
    DocumentParseRequest,
    DocumentParseResponse,
    DocumentRestoreRequest,
    DocumentUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.document_form_options_service import (
    DocumentFormOptionsService,
)
from app.services.documents.document_service import DocumentService

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW)),
]
Creator = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_CREATE)),
]
Updater = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_UPDATE)),
]
Archiver = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_ARCHIVE)),
]
Restorer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_RESTORE)),
]
RevisionManager = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_MANAGE_REVISIONS)),
]


def _service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> DocumentService:
    return DocumentService(session, settings, user, metadata)


# Static POST routes must precede /{document_id}.
@router.get(
    "/form-options",
    response_model=ApiResponse[DocumentFormOptionsResponse],
)
async def document_form_options(
    session: Session,
    settings: Configuration,
    user: Viewer,
) -> ApiResponse[DocumentFormOptionsResponse]:
    data = await DocumentFormOptionsService(
        session,
        settings,
        user,
    ).get()
    return ApiResponse(
        success=True,
        message="Document form options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/parse-code",
    response_model=ApiResponse[DocumentParseResponse],
)
async def parse_document_code(
    payload: DocumentParseRequest,
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentParseResponse]:
    data = await _service(session, settings, user, metadata).parse_code(
        payload.value
    )
    return ApiResponse(
        success=True,
        message="Document code parsed successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/bulk/archive",
    response_model=ApiResponse[BulkDocumentResult],
)
async def bulk_archive_documents(
    payload: BulkArchiveRequest,
    session: Session,
    settings: Configuration,
    user: Archiver,
    metadata: Metadata,
) -> ApiResponse[BulkDocumentResult]:
    data = await _service(
        session, settings, user, metadata
    ).bulk_archive(payload)
    return ApiResponse(
        success=True,
        message="Bulk archive completed.",
        data=data,
        errors=None,
    )


@router.post(
    "/bulk/restore",
    response_model=ApiResponse[BulkDocumentResult],
)
async def bulk_restore_documents(
    payload: BulkRestoreRequest,
    session: Session,
    settings: Configuration,
    user: Restorer,
    metadata: Metadata,
) -> ApiResponse[BulkDocumentResult]:
    data = await _service(
        session, settings, user, metadata
    ).bulk_restore(payload)
    return ApiResponse(
        success=True,
        message="Bulk restore completed.",
        data=data,
        errors=None,
    )


@router.post(
    "/bulk/update-status",
    response_model=ApiResponse[BulkDocumentResult],
)
async def bulk_update_document_status(
    payload: BulkUpdateStatusRequest,
    session: Session,
    settings: Configuration,
    user: RevisionManager,
    metadata: Metadata,
) -> ApiResponse[BulkDocumentResult]:
    data = await _service(
        session, settings, user, metadata
    ).bulk_update_status(payload)
    return ApiResponse(
        success=True,
        message="Bulk status update completed.",
        data=data,
        errors=None,
    )


@router.get(
    "",
    response_model=ApiResponse[DocumentListResponse],
)
async def list_documents(
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
    search: str | None = None,
    base_document_code: Annotated[
        str | None,
        Query(alias="baseDocumentCode", min_length=1, max_length=255),
    ] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    section_id: Annotated[
        UUID | None,
        Query(alias="sectionId"),
    ] = None,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    document_status_id: Annotated[
        UUID | None,
        Query(alias="documentStatusId"),
    ] = None,
    validation_rule_id: Annotated[
        UUID | None,
        Query(alias="validationRuleId"),
    ] = None,
    revision_code: Annotated[
        str | None,
        Query(alias="revisionCode"),
    ] = None,
    company_code: Annotated[
        str | None,
        Query(alias="companyCode"),
    ] = None,
    is_archived: Annotated[
        bool,
        Query(alias="isArchived"),
    ] = False,
    has_sharepoint_url: Annotated[
        bool | None,
        Query(alias="hasSharePointUrl"),
    ] = None,
    created_by: Annotated[
        UUID | None,
        Query(alias="createdBy"),
    ] = None,
    created_from: Annotated[
        date | None,
        Query(alias="createdFrom"),
    ] = None,
    created_to: Annotated[
        date | None,
        Query(alias="createdTo"),
    ] = None,
    effective_from: Annotated[
        date | None,
        Query(alias="effectiveFrom"),
    ] = None,
    effective_to: Annotated[
        date | None,
        Query(alias="effectiveTo"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "baseDocumentCode",
            "title",
            "companyCode",
            "department",
            "documentType",
            "createdAt",
            "updatedAt",
            "effectiveDate",
        ],
        Query(alias="sortBy"),
    ] = "updatedAt",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> ApiResponse[DocumentListResponse]:
    filters = DocumentFilter(
        search=search,
        base_document_code=base_document_code,
        department_id=department_id,
        section_id=section_id,
        document_type_id=document_type_id,
        document_status_id=document_status_id,
        validation_rule_id=validation_rule_id,
        revision_code=revision_code,
        company_code=company_code,
        is_archived=is_archived,
        has_sharepoint_url=has_sharepoint_url,
        created_by=created_by,
        created_from=created_from,
        created_to=created_to,
        effective_from=effective_from,
        effective_to=effective_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    data = await _service(session, settings, user, metadata).list(filters)
    return ApiResponse(
        success=True,
        message="Documents retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "",
    response_model=ApiResponse[DocumentDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    payload: DocumentCreate,
    session: Session,
    settings: Configuration,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[DocumentDetailResponse]:
    data = await _service(
        session, settings, user, metadata
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Document created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/{document_id}",
    response_model=ApiResponse[DocumentDetailResponse],
)
async def get_document(
    document_id: UUID,
    session: Session,
    settings: Configuration,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentDetailResponse]:
    data = await _service(session, settings, user, metadata).get(document_id)
    return ApiResponse(
        success=True,
        message="Document retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/{document_id}",
    response_model=ApiResponse[DocumentDetailResponse],
)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    session: Session,
    settings: Configuration,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DocumentDetailResponse]:
    data = await _service(
        session, settings, user, metadata
    ).update(document_id, payload)
    return ApiResponse(
        success=True,
        message="Document updated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{document_id}/archive",
    response_model=ApiResponse[DocumentDetailResponse],
)
async def archive_document(
    document_id: UUID,
    payload: DocumentArchiveRequest,
    session: Session,
    settings: Configuration,
    user: Archiver,
    metadata: Metadata,
) -> ApiResponse[DocumentDetailResponse]:
    data = await _service(
        session, settings, user, metadata
    ).archive(document_id, payload)
    return ApiResponse(
        success=True,
        message="Document archived successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{document_id}/restore",
    response_model=ApiResponse[DocumentDetailResponse],
)
async def restore_document(
    document_id: UUID,
    session: Session,
    settings: Configuration,
    user: Restorer,
    metadata: Metadata,
    payload: DocumentRestoreRequest | None = None,
) -> ApiResponse[DocumentDetailResponse]:
    data = await _service(
        session, settings, user, metadata
    ).restore(document_id, payload)
    return ApiResponse(
        success=True,
        message="Document restored successfully.",
        data=data,
        errors=None,
    )
