"""Phase 9 glossary management, import/export, validation, and history APIs."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.glossary_enums import (
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossaryScopeType,
    GlossaryTermType,
    GlossaryValidationStatus,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.glossary import (
    GlossaryExceptionCreate,
    GlossaryExceptionListResponse,
    GlossaryExceptionResponse,
    GlossaryExceptionUpdate,
    GlossaryImportConfirmResponse,
    GlossaryImportMode,
    GlossaryImportPreviewResponse,
    GlossaryProfileCreate,
    GlossaryProfileListResponse,
    GlossaryProfileResponse,
    GlossaryProfileUpdate,
    GlossaryTermCreate,
    GlossaryTermListResponse,
    GlossaryTermResponse,
    GlossaryTermUpdate,
    GlossaryTestMatchRequest,
    GlossaryTestMatchResponse,
    GlossaryTranslationCreate,
    GlossaryTranslationResponse,
    GlossaryTranslationUpdate,
    GlossaryVariantCreate,
    GlossaryVariantResponse,
    GlossaryVariantUpdate,
)
from app.schemas.glossary_validation import (
    GlossaryFindingListResponse,
    GlossaryMatchListResponse,
    GlossaryRevalidationRequest,
    GlossaryValidationHistoryResponse,
    GlossaryValidationJobListResponse,
    GlossaryValidationQueuedResponse,
    GlossaryValidationRequest,
    GlossaryValidationRunResponse,
    GlossaryValidationSummaryResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.glossary_exception_service import (
    GlossaryExceptionManagementService,
)
from app.services.glossary.glossary_export_service import (
    GlossaryExportService,
)
from app.services.glossary.glossary_import_service import (
    GlossaryImportService,
)
from app.services.glossary.glossary_job_service import GlossaryJobService
from app.services.glossary.glossary_profile_service import (
    GlossaryProfileService,
)
from app.services.glossary.glossary_service import GlossaryService
from app.services.glossary.glossary_summary_service import (
    GlossarySummaryService,
)
from app.services.glossary.glossary_validation_export_service import (
    GlossaryValidationExportService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
GlossaryViewer = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_VIEW)),
]
GlossaryCreator = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_CREATE)),
]
GlossaryUpdater = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_UPDATE)),
]
GlossaryImporter = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_IMPORT)),
]
GlossaryExporter = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_EXPORT)),
]
GlossaryValidator = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_VALIDATE)),
]
GlossaryExceptionManager = Annotated[
    User,
    Depends(require_permissions(Permission.GLOSSARY_MANAGE_EXCEPTIONS)),
]


def _profile_service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> GlossaryProfileService:
    return GlossaryProfileService(session, user, metadata)


def _term_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> GlossaryService:
    return GlossaryService(
        session,
        user,
        metadata,
        term_max_length=getattr(settings, "glossary_term_max_length", 500),
        regex_max_length=getattr(settings, "glossary_regex_max_length", 500),
        regex_timeout_ms=getattr(settings, "glossary_regex_timeout_ms", 100),
    )


def _exception_service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> GlossaryExceptionManagementService:
    return GlossaryExceptionManagementService(session, user, metadata)


def _job_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> GlossaryJobService:
    return GlossaryJobService(session, settings, user, metadata)


def _summary_service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> GlossarySummaryService:
    return GlossarySummaryService(session, user, metadata)


@router.get(
    "/glossary/profiles",
    response_model=ApiResponse[GlossaryProfileListResponse],
)
async def list_glossary_profiles(
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    scope_type: Annotated[
        GlossaryScopeType | None,
        Query(alias="scopeType"),
    ] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    sort_by: Annotated[
        Literal["code", "name", "scopeType", "updatedAt"],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "asc",
) -> ApiResponse[GlossaryProfileListResponse]:
    data = await _profile_service(session, user, metadata).list(
        search=search,
        scope_type=scope_type,
        department_id=department_id,
        document_type_id=document_type_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Glossary profiles retrieved.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/profiles",
    response_model=ApiResponse[GlossaryProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_glossary_profile(
    payload: GlossaryProfileCreate,
    session: Session,
    user: GlossaryCreator,
    metadata: Metadata,
) -> ApiResponse[GlossaryProfileResponse]:
    data = await _profile_service(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Glossary profile created.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/profiles/{profile_id}",
    response_model=ApiResponse[GlossaryProfileResponse],
)
async def get_glossary_profile(
    profile_id: UUID,
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryProfileResponse]:
    data = await _profile_service(session, user, metadata).get(profile_id)
    return ApiResponse(
        success=True,
        message="Glossary profile retrieved.",
        data=data,
        errors=None,
    )


@router.put(
    "/glossary/profiles/{profile_id}",
    response_model=ApiResponse[GlossaryProfileResponse],
)
async def update_glossary_profile(
    profile_id: UUID,
    payload: GlossaryProfileUpdate,
    session: Session,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryProfileResponse]:
    data = await _profile_service(session, user, metadata).update(
        profile_id,
        payload,
    )
    return ApiResponse(
        success=True,
        message="Glossary profile updated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/profiles/{profile_id}/archive",
    response_model=ApiResponse[GlossaryProfileResponse],
)
async def archive_glossary_profile(
    profile_id: UUID,
    session: Session,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryProfileResponse]:
    data = await _profile_service(session, user, metadata).archive(
        profile_id
    )
    return ApiResponse(
        success=True,
        message="Glossary profile archived.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/profiles/{profile_id}/restore",
    response_model=ApiResponse[GlossaryProfileResponse],
)
async def restore_glossary_profile(
    profile_id: UUID,
    session: Session,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryProfileResponse]:
    data = await _profile_service(session, user, metadata).restore(
        profile_id
    )
    return ApiResponse(
        success=True,
        message="Glossary profile restored.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/terms",
    response_model=ApiResponse[GlossaryTermListResponse],
)
async def list_glossary_terms(
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    profile_id: Annotated[
        UUID | None,
        Query(alias="profileId"),
    ] = None,
    term_type: Annotated[
        GlossaryTermType | None,
        Query(alias="termType"),
    ] = None,
    language_code: Annotated[
        GlossaryLanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    sort_by: Annotated[
        Literal["termCode", "conceptName", "termType", "updatedAt"],
        Query(alias="sortBy"),
    ] = "termCode",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "asc",
) -> ApiResponse[GlossaryTermListResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).list(
        search=search,
        profile_id=profile_id,
        term_type=term_type,
        language_code=language_code,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Glossary terms retrieved.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/terms",
    response_model=ApiResponse[GlossaryTermResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_glossary_term(
    payload: GlossaryTermCreate,
    session: Session,
    settings: Configuration,
    user: GlossaryCreator,
    metadata: Metadata,
) -> ApiResponse[GlossaryTermResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Glossary term created.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/terms/{term_id}",
    response_model=ApiResponse[GlossaryTermResponse],
)
async def get_glossary_term(
    term_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryTermResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).get(term_id)
    return ApiResponse(
        success=True,
        message="Glossary term retrieved.",
        data=data,
        errors=None,
    )


@router.put(
    "/glossary/terms/{term_id}",
    response_model=ApiResponse[GlossaryTermResponse],
)
async def update_glossary_term(
    term_id: UUID,
    payload: GlossaryTermUpdate,
    session: Session,
    settings: Configuration,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryTermResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).update(term_id, payload)
    return ApiResponse(
        success=True,
        message="Glossary term updated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/terms/{term_id}/archive",
    response_model=ApiResponse[GlossaryTermResponse],
)
async def archive_glossary_term(
    term_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryTermResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).archive(term_id)
    return ApiResponse(
        success=True,
        message="Glossary term archived.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/terms/{term_id}/restore",
    response_model=ApiResponse[GlossaryTermResponse],
)
async def restore_glossary_term(
    term_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryTermResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).restore(term_id)
    return ApiResponse(
        success=True,
        message="Glossary term restored.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/terms/{term_id}/translations",
    response_model=ApiResponse[GlossaryTranslationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_glossary_translation(
    term_id: UUID,
    payload: GlossaryTranslationCreate,
    session: Session,
    settings: Configuration,
    user: GlossaryCreator,
    metadata: Metadata,
) -> ApiResponse[GlossaryTranslationResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).add_translation(term_id, payload)
    return ApiResponse(
        success=True,
        message="Glossary translation created.",
        data=data,
        errors=None,
    )


@router.put(
    "/glossary/translations/{translation_id}",
    response_model=ApiResponse[GlossaryTranslationResponse],
)
async def update_glossary_translation(
    translation_id: UUID,
    payload: GlossaryTranslationUpdate,
    session: Session,
    settings: Configuration,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryTranslationResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).update_translation(translation_id, payload)
    return ApiResponse(
        success=True,
        message="Glossary translation updated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/translations/{translation_id}/variants",
    response_model=ApiResponse[GlossaryVariantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_glossary_variant(
    translation_id: UUID,
    payload: GlossaryVariantCreate,
    session: Session,
    settings: Configuration,
    user: GlossaryCreator,
    metadata: Metadata,
) -> ApiResponse[GlossaryVariantResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).add_variant(translation_id, payload)
    return ApiResponse(
        success=True,
        message="Glossary variant created.",
        data=data,
        errors=None,
    )


@router.put(
    "/glossary/variants/{variant_id}",
    response_model=ApiResponse[GlossaryVariantResponse],
)
async def update_glossary_variant(
    variant_id: UUID,
    payload: GlossaryVariantUpdate,
    session: Session,
    settings: Configuration,
    user: GlossaryUpdater,
    metadata: Metadata,
) -> ApiResponse[GlossaryVariantResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).update_variant(variant_id, payload)
    return ApiResponse(
        success=True,
        message="Glossary variant updated.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/exceptions",
    response_model=ApiResponse[GlossaryExceptionListResponse],
)
async def list_glossary_exceptions(
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
    term_id: Annotated[UUID | None, Query(alias="termId")] = None,
    scope_type: Annotated[
        GlossaryExceptionScopeType | None,
        Query(alias="scopeType"),
    ] = None,
    exception_type: Annotated[
        GlossaryExceptionType | None,
        Query(alias="exceptionType"),
    ] = None,
    language_code: Annotated[
        GlossaryLanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    effective_on: Annotated[
        date | None,
        Query(alias="effectiveOn"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[GlossaryExceptionListResponse]:
    data = await _exception_service(session, user, metadata).list(
        term_id=term_id,
        scope_type=scope_type,
        exception_type=exception_type,
        language_code=language_code,
        is_active=is_active,
        effective_on=effective_on,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Glossary exceptions retrieved.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/exceptions",
    response_model=ApiResponse[GlossaryExceptionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_glossary_exception(
    payload: GlossaryExceptionCreate,
    session: Session,
    user: GlossaryExceptionManager,
    metadata: Metadata,
) -> ApiResponse[GlossaryExceptionResponse]:
    data = await _exception_service(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Glossary exception created.",
        data=data,
        errors=None,
    )


@router.put(
    "/glossary/exceptions/{exception_id}",
    response_model=ApiResponse[GlossaryExceptionResponse],
)
async def update_glossary_exception(
    exception_id: UUID,
    payload: GlossaryExceptionUpdate,
    session: Session,
    user: GlossaryExceptionManager,
    metadata: Metadata,
) -> ApiResponse[GlossaryExceptionResponse]:
    data = await _exception_service(session, user, metadata).update(
        exception_id,
        payload,
    )
    return ApiResponse(
        success=True,
        message="Glossary exception updated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/exceptions/{exception_id}/deactivate",
    response_model=ApiResponse[GlossaryExceptionResponse],
)
async def deactivate_glossary_exception(
    exception_id: UUID,
    session: Session,
    user: GlossaryExceptionManager,
    metadata: Metadata,
) -> ApiResponse[GlossaryExceptionResponse]:
    data = await _exception_service(session, user, metadata).deactivate(
        exception_id
    )
    return ApiResponse(
        success=True,
        message="Glossary exception deactivated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/test-match",
    response_model=ApiResponse[GlossaryTestMatchResponse],
)
async def test_glossary_match(
    payload: GlossaryTestMatchRequest,
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryTestMatchResponse]:
    data = await _term_service(
        session,
        settings,
        user,
        metadata,
    ).test_match(payload)
    return ApiResponse(
        success=True,
        message="Glossary match test completed locally.",
        data=data,
        errors=None,
    )


@router.get("/glossary/import/template")
async def download_glossary_template(
    user: GlossaryImporter,
) -> StreamingResponse:
    del user
    content, filename = GlossaryImportService.template()
    return StreamingResponse(
        BytesIO(content),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post(
    "/glossary/import/preview",
    response_model=ApiResponse[GlossaryImportPreviewResponse],
)
async def preview_glossary_import(
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: Configuration,
    user: GlossaryImporter,
    metadata: Metadata,
) -> ApiResponse[GlossaryImportPreviewResponse]:
    content = await file.read()
    await file.close()
    service = GlossaryImportService(
        session,
        user,
        metadata,
        maximum_rows=getattr(
            settings,
            "glossary_import_max_rows",
            100_000,
        ),
        regex_max_length=getattr(
            settings,
            "glossary_regex_max_length",
            500,
        ),
        regex_timeout_ms=getattr(
            settings,
            "glossary_regex_timeout_ms",
            100,
        ),
    )
    data = await service.preview(filename=file.filename, content=content)
    return ApiResponse(
        success=True,
        message="Glossary import preview generated.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/import/confirm",
    response_model=ApiResponse[GlossaryImportConfirmResponse],
)
async def confirm_glossary_import(
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: Configuration,
    user: GlossaryImporter,
    metadata: Metadata,
    mode: Annotated[GlossaryImportMode, Form()] = (
        GlossaryImportMode.CREATE_ONLY
    ),
) -> ApiResponse[GlossaryImportConfirmResponse]:
    content = await file.read()
    await file.close()
    service = GlossaryImportService(
        session,
        user,
        metadata,
        maximum_rows=getattr(
            settings,
            "glossary_import_max_rows",
            100_000,
        ),
        regex_max_length=getattr(
            settings,
            "glossary_regex_max_length",
            500,
        ),
        regex_timeout_ms=getattr(
            settings,
            "glossary_regex_timeout_ms",
            100,
        ),
    )
    data = await service.confirm(
        mode=mode,
        filename=file.filename,
        content=content,
    )
    return ApiResponse(
        success=True,
        message="Glossary workbook imported.",
        data=data,
        errors=None,
    )


@router.get("/glossary/export")
async def export_glossary(
    session: Session,
    settings: Configuration,
    user: GlossaryExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["xlsx", "json"],
        Query(alias="format"),
    ] = "xlsx",
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    profile_ids: Annotated[
        list[UUID] | None,
        Query(alias="profileIds"),
    ] = None,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
) -> StreamingResponse:
    content, filename, media_type = await GlossaryExportService(
        session,
        user,
        metadata,
        maximum_rows=getattr(
            settings,
            "glossary_import_max_rows",
            100_000,
        ),
    ).export(
        export_format=export_format,
        department_id=department_id,
        profile_ids=profile_ids,
        include_inactive=include_inactive,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post(
    "/glossary/validation/jobs",
    response_model=ApiResponse[GlossaryValidationQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_glossary_validation(
    payload: GlossaryValidationRequest,
    session: Session,
    settings: Configuration,
    user: GlossaryValidator,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).start(
        document_file_id=payload.document_file_id,
        compliance_run_id=payload.compliance_run_id,
        profile_ids=payload.profile_ids,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "Equivalent glossary validation result reused."
            if data.reused_existing_result
            else "Glossary validation queued."
        ),
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/jobs",
    response_model=ApiResponse[GlossaryValidationJobListResponse],
)
async def list_glossary_validation_jobs(
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    document_id: Annotated[UUID | None, Query(alias="documentId")] = None,
    document_file_id: Annotated[
        UUID | None,
        Query(alias="documentFileId"),
    ] = None,
    job_status: Annotated[
        GlossaryValidationStatus | None,
        Query(alias="status"),
    ] = None,
    requested_by: Annotated[
        UUID | None,
        Query(alias="requestedBy"),
    ] = None,
    requested_from: Annotated[
        datetime | None,
        Query(alias="requestedFrom"),
    ] = None,
    requested_to: Annotated[
        datetime | None,
        Query(alias="requestedTo"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[GlossaryValidationJobListResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).list(
        search=search,
        document_id=document_id,
        document_file_id=document_file_id,
        status=job_status,
        requested_by=requested_by,
        requested_from=requested_from,
        requested_to=requested_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Glossary validation jobs retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/jobs/{job_id}",
    response_model=ApiResponse[GlossaryValidationRunResponse],
)
async def get_glossary_validation_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationRunResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).get(job_id)
    return ApiResponse(
        success=True,
        message="Glossary validation job retrieved.",
        data=data,
        errors=None,
    )


@router.post(
    "/glossary/validation/jobs/{job_id}/cancel",
    response_model=ApiResponse[GlossaryValidationRunResponse],
)
async def cancel_glossary_validation_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryValidator,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationRunResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Glossary validation cancellation requested.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/runs/{run_id}",
    response_model=ApiResponse[GlossaryValidationRunResponse],
)
async def get_glossary_validation_run(
    run_id: UUID,
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationRunResponse]:
    data = await _summary_service(session, user, metadata).run(run_id)
    return ApiResponse(
        success=True,
        message="Glossary validation run retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/runs/{run_id}/summary",
    response_model=ApiResponse[GlossaryValidationSummaryResponse],
)
async def get_glossary_validation_summary(
    run_id: UUID,
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationSummaryResponse]:
    data = await _summary_service(session, user, metadata).summary(run_id)
    return ApiResponse(
        success=True,
        message="Glossary validation summary retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/runs/{run_id}/matches",
    response_model=ApiResponse[GlossaryMatchListResponse],
)
async def list_glossary_validation_matches(
    run_id: UUID,
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
    language_code: Annotated[
        GlossaryLanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    term_id: Annotated[UUID | None, Query(alias="termId")] = None,
    match_type: Annotated[
        GlossaryMatchType | None,
        Query(alias="matchType"),
    ] = None,
    is_preferred: Annotated[
        bool | None,
        Query(alias="isPreferred"),
    ] = None,
    is_forbidden: Annotated[
        bool | None,
        Query(alias="isForbidden"),
    ] = None,
    has_exception: Annotated[
        bool | None,
        Query(alias="hasException"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[GlossaryMatchListResponse]:
    data = await _summary_service(
        session,
        user,
        metadata,
    ).list_matches(
        run_id,
        language_code=language_code,
        term_id=term_id,
        match_type=match_type,
        is_preferred=is_preferred,
        is_forbidden=is_forbidden,
        has_exception=has_exception,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Glossary validation matches retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/glossary/validation/runs/{run_id}/findings",
    response_model=ApiResponse[GlossaryFindingListResponse],
)
async def list_glossary_validation_findings(
    run_id: UUID,
    session: Session,
    user: GlossaryViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[GlossaryFindingListResponse]:
    data = await _summary_service(
        session,
        user,
        metadata,
    ).list_findings(run_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Glossary validation findings retrieved.",
        data=data,
        errors=None,
    )


@router.get("/glossary/validation/runs/{run_id}/export")
async def export_glossary_validation(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["xlsx", "json"],
        Query(alias="format"),
    ] = "xlsx",
) -> StreamingResponse:
    content, filename, media_type = await GlossaryValidationExportService(
        session,
        user,
        metadata,
        maximum_rows=getattr(
            settings,
            "glossary_import_max_rows",
            100_000,
        ),
    ).export(run_id, export_format=export_format)
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post(
    "/glossary/validation/runs/{run_id}/revalidate",
    response_model=ApiResponse[GlossaryValidationQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def revalidate_glossary(
    run_id: UUID,
    payload: GlossaryRevalidationRequest,
    session: Session,
    settings: Configuration,
    user: GlossaryValidator,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).revalidate(
        run_id,
        reason=payload.reason,
        profile_ids=payload.profile_ids,
    )
    return ApiResponse(
        success=True,
        message="Glossary revalidation queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/glossary-validation",
    response_model=ApiResponse[GlossaryValidationRunResponse],
)
async def get_current_file_glossary_validation(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
) -> ApiResponse[GlossaryValidationRunResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).current(file_id)
    return ApiResponse(
        success=True,
        message="Current glossary validation retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/glossary-history",
    response_model=ApiResponse[GlossaryValidationHistoryResponse],
)
async def get_file_glossary_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: GlossaryViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[GlossaryValidationHistoryResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).history(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Glossary validation history retrieved.",
        data=data,
        errors=None,
    )
