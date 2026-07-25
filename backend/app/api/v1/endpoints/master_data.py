"""Thin Phase 3 master-data HTTP endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.department import (
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.document_status import (
    DocumentStatusCreate,
    DocumentStatusListResponse,
    DocumentStatusResponse,
    DocumentStatusUpdate,
)
from app.schemas.document_type import (
    DocumentTypeCategory,
    DocumentTypeCreate,
    DocumentTypeListResponse,
    DocumentTypeResponse,
    DocumentTypeUpdate,
)
from app.schemas.master_data import MasterDataOption, MasterDataOverview
from app.schemas.section import (
    SectionCreate,
    SectionListResponse,
    SectionResponse,
    SectionUpdate,
)
from app.schemas.validation_rule import (
    ValidationRuleCreate,
    ValidationRuleListResponse,
    ValidationRuleResponse,
    ValidationRuleUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.department_service import DepartmentService
from app.services.master_data.document_status_service import (
    DocumentStatusService,
)
from app.services.master_data.document_type_service import DocumentTypeService
from app.services.master_data.overview_service import MasterDataOverviewService
from app.services.master_data.section_service import SectionService
from app.services.master_data.validation_rule_service import (
    ValidationRuleService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Viewer = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_VIEW)),
]
Creator = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_CREATE)),
]
Updater = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_UPDATE)),
]
Deleter = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_DELETE)),
]

SortOrder = Literal["asc", "desc"]


@router.get(
    "/overview",
    response_model=ApiResponse[MasterDataOverview],
)
async def overview(
    session: Session,
    _: Viewer,
) -> ApiResponse[MasterDataOverview]:
    data = await MasterDataOverviewService(session).get()
    return ApiResponse(
        success=True,
        message="Master data overview retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/departments/options",
    response_model=ApiResponse[list[MasterDataOption]],
)
async def department_options(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> ApiResponse[list[MasterDataOption]]:
    data = await DepartmentService(session, user, metadata).options(
        active_only=active_only
    )
    return ApiResponse(
        success=True,
        message="Department options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/departments",
    response_model=ApiResponse[DepartmentListResponse],
)
async def list_departments(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    search: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal["code", "name", "isActive", "createdAt", "updatedAt"],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[DepartmentListResponse]:
    data = await DepartmentService(session, user, metadata).list(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Departments retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/departments",
    response_model=ApiResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    payload: DepartmentCreate,
    session: Session,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[DepartmentResponse]:
    data = await DepartmentService(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Department created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/departments/{entity_id}",
    response_model=ApiResponse[DepartmentResponse],
)
async def get_department(
    entity_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DepartmentResponse]:
    data = await DepartmentService(session, user, metadata).get(entity_id)
    return ApiResponse(
        success=True,
        message="Department retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/departments/{entity_id}",
    response_model=ApiResponse[DepartmentResponse],
)
async def update_department(
    entity_id: UUID,
    payload: DepartmentUpdate,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DepartmentResponse]:
    data = await DepartmentService(session, user, metadata).update(
        entity_id,
        payload,
    )
    return ApiResponse(
        success=True,
        message="Department updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/departments/{entity_id}/activate",
    response_model=ApiResponse[DepartmentResponse],
)
async def activate_department(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DepartmentResponse]:
    data, _ = await DepartmentService(session, user, metadata).set_active(
        entity_id,
        active=True,
    )
    return ApiResponse(
        success=True,
        message="Department activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/departments/{entity_id}/deactivate",
    response_model=ApiResponse[DepartmentResponse],
)
async def deactivate_department(
    entity_id: UUID,
    session: Session,
    user: Deleter,
    metadata: Metadata,
) -> ApiResponse[DepartmentResponse]:
    data, active_sections = await DepartmentService(
        session, user, metadata
    ).set_active(entity_id, active=False)
    warning = (
        f" {active_sections} active sections remain assigned."
        if active_sections
        else ""
    )
    return ApiResponse(
        success=True,
        message=f"Department deactivated successfully.{warning}",
        data=data,
        errors=None,
    )


@router.get(
    "/sections/options",
    response_model=ApiResponse[list[MasterDataOption]],
)
async def section_options(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> ApiResponse[list[MasterDataOption]]:
    data = await SectionService(session, user, metadata).options(
        department_id=department_id,
        active_only=active_only,
    )
    return ApiResponse(
        success=True,
        message="Section options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/sections",
    response_model=ApiResponse[SectionListResponse],
)
async def list_sections(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    search: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "code",
            "name",
            "departmentId",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[SectionListResponse]:
    data = await SectionService(session, user, metadata).list(
        department_id=department_id,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Sections retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/sections",
    response_model=ApiResponse[SectionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    payload: SectionCreate,
    session: Session,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[SectionResponse]:
    data = await SectionService(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Section created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/sections/{entity_id}",
    response_model=ApiResponse[SectionResponse],
)
async def get_section(
    entity_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[SectionResponse]:
    data = await SectionService(session, user, metadata).get(entity_id)
    return ApiResponse(
        success=True,
        message="Section retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/sections/{entity_id}",
    response_model=ApiResponse[SectionResponse],
)
async def update_section(
    entity_id: UUID,
    payload: SectionUpdate,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[SectionResponse]:
    data = await SectionService(session, user, metadata).update(
        entity_id, payload
    )
    return ApiResponse(
        success=True,
        message="Section updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/sections/{entity_id}/activate",
    response_model=ApiResponse[SectionResponse],
)
async def activate_section(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[SectionResponse]:
    data = await SectionService(session, user, metadata).set_active(
        entity_id, active=True
    )
    return ApiResponse(
        success=True,
        message="Section activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/sections/{entity_id}/deactivate",
    response_model=ApiResponse[SectionResponse],
)
async def deactivate_section(
    entity_id: UUID,
    session: Session,
    user: Deleter,
    metadata: Metadata,
) -> ApiResponse[SectionResponse]:
    data = await SectionService(session, user, metadata).set_active(
        entity_id, active=False
    )
    return ApiResponse(
        success=True,
        message="Section deactivated successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-types/options",
    response_model=ApiResponse[list[MasterDataOption]],
)
async def document_type_options(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> ApiResponse[list[MasterDataOption]]:
    data = await DocumentTypeService(session, user, metadata).options(
        active_only=active_only
    )
    return ApiResponse(
        success=True,
        message="Document type options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-types",
    response_model=ApiResponse[DocumentTypeListResponse],
)
async def list_document_types(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    search: str | None = None,
    category: DocumentTypeCategory | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "code",
            "name",
            "category",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[DocumentTypeListResponse]:
    data = await DocumentTypeService(session, user, metadata).list(
        search=search,
        category=category.value if category is not None else None,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Document types retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/document-types",
    response_model=ApiResponse[DocumentTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_document_type(
    payload: DocumentTypeCreate,
    session: Session,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[DocumentTypeResponse]:
    data = await DocumentTypeService(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Document type created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-types/{entity_id}",
    response_model=ApiResponse[DocumentTypeResponse],
)
async def get_document_type(
    entity_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentTypeResponse]:
    data = await DocumentTypeService(session, user, metadata).get(entity_id)
    return ApiResponse(
        success=True,
        message="Document type retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/document-types/{entity_id}",
    response_model=ApiResponse[DocumentTypeResponse],
)
async def update_document_type(
    entity_id: UUID,
    payload: DocumentTypeUpdate,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DocumentTypeResponse]:
    data = await DocumentTypeService(session, user, metadata).update(
        entity_id, payload
    )
    return ApiResponse(
        success=True,
        message="Document type updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/document-types/{entity_id}/activate",
    response_model=ApiResponse[DocumentTypeResponse],
)
async def activate_document_type(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DocumentTypeResponse]:
    data = await DocumentTypeService(session, user, metadata).set_active(
        entity_id, active=True
    )
    return ApiResponse(
        success=True,
        message="Document type activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/document-types/{entity_id}/deactivate",
    response_model=ApiResponse[DocumentTypeResponse],
)
async def deactivate_document_type(
    entity_id: UUID,
    session: Session,
    user: Deleter,
    metadata: Metadata,
) -> ApiResponse[DocumentTypeResponse]:
    data = await DocumentTypeService(session, user, metadata).set_active(
        entity_id, active=False
    )
    return ApiResponse(
        success=True,
        message="Document type deactivated successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-statuses/options",
    response_model=ApiResponse[list[MasterDataOption]],
)
async def document_status_options(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> ApiResponse[list[MasterDataOption]]:
    data = await DocumentStatusService(session, user, metadata).options(
        active_only=active_only
    )
    return ApiResponse(
        success=True,
        message="Document status options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-statuses",
    response_model=ApiResponse[DocumentStatusListResponse],
)
async def list_document_statuses(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    search: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "code",
            "name",
            "displayOrder",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "displayOrder",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[DocumentStatusListResponse]:
    data = await DocumentStatusService(session, user, metadata).list(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Document statuses retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/document-statuses",
    response_model=ApiResponse[DocumentStatusResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_document_status(
    payload: DocumentStatusCreate,
    session: Session,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[DocumentStatusResponse]:
    data = await DocumentStatusService(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Document status created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-statuses/{entity_id}",
    response_model=ApiResponse[DocumentStatusResponse],
)
async def get_document_status(
    entity_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[DocumentStatusResponse]:
    data = await DocumentStatusService(session, user, metadata).get(entity_id)
    return ApiResponse(
        success=True,
        message="Document status retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/document-statuses/{entity_id}",
    response_model=ApiResponse[DocumentStatusResponse],
)
async def update_document_status(
    entity_id: UUID,
    payload: DocumentStatusUpdate,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DocumentStatusResponse]:
    data = await DocumentStatusService(session, user, metadata).update(
        entity_id, payload
    )
    return ApiResponse(
        success=True,
        message="Document status updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/document-statuses/{entity_id}/activate",
    response_model=ApiResponse[DocumentStatusResponse],
)
async def activate_document_status(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[DocumentStatusResponse]:
    data = await DocumentStatusService(session, user, metadata).set_active(
        entity_id, active=True
    )
    return ApiResponse(
        success=True,
        message="Document status activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/document-statuses/{entity_id}/deactivate",
    response_model=ApiResponse[DocumentStatusResponse],
)
async def deactivate_document_status(
    entity_id: UUID,
    session: Session,
    user: Deleter,
    metadata: Metadata,
) -> ApiResponse[DocumentStatusResponse]:
    data = await DocumentStatusService(session, user, metadata).set_active(
        entity_id, active=False
    )
    return ApiResponse(
        success=True,
        message="Document status deactivated successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/validation-rules/options",
    response_model=ApiResponse[list[MasterDataOption]],
)
async def validation_rule_options(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> ApiResponse[list[MasterDataOption]]:
    data = await ValidationRuleService(session, user, metadata).options(
        active_only=active_only
    )
    return ApiResponse(
        success=True,
        message="Validation rule options retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/validation-rules",
    response_model=ApiResponse[ValidationRuleListResponse],
)
async def list_validation_rules(
    session: Session,
    user: Viewer,
    metadata: Metadata,
    document_type_id: Annotated[
        UUID | None,
        Query(alias="documentTypeId"),
    ] = None,
    search: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    is_default: Annotated[bool | None, Query(alias="isDefault")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "code",
            "name",
            "documentTypeId",
            "isDefault",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[ValidationRuleListResponse]:
    data = await ValidationRuleService(session, user, metadata).list(
        document_type_id=document_type_id,
        search=search,
        is_active=is_active,
        is_default=is_default,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Validation rules retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/validation-rules",
    response_model=ApiResponse[ValidationRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_rule(
    payload: ValidationRuleCreate,
    session: Session,
    user: Creator,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Validation rule created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/validation-rules/{entity_id}",
    response_model=ApiResponse[ValidationRuleResponse],
)
async def get_validation_rule(
    entity_id: UUID,
    session: Session,
    user: Viewer,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).get(entity_id)
    return ApiResponse(
        success=True,
        message="Validation rule retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/validation-rules/{entity_id}",
    response_model=ApiResponse[ValidationRuleResponse],
)
async def update_validation_rule(
    entity_id: UUID,
    payload: ValidationRuleUpdate,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).update(
        entity_id, payload
    )
    return ApiResponse(
        success=True,
        message="Validation rule updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/validation-rules/{entity_id}/activate",
    response_model=ApiResponse[ValidationRuleResponse],
)
async def activate_validation_rule(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).set_active(
        entity_id, active=True
    )
    return ApiResponse(
        success=True,
        message="Validation rule activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/validation-rules/{entity_id}/deactivate",
    response_model=ApiResponse[ValidationRuleResponse],
)
async def deactivate_validation_rule(
    entity_id: UUID,
    session: Session,
    user: Deleter,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).set_active(
        entity_id, active=False
    )
    return ApiResponse(
        success=True,
        message="Validation rule deactivated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/validation-rules/{entity_id}/set-default",
    response_model=ApiResponse[ValidationRuleResponse],
)
async def set_default_validation_rule(
    entity_id: UUID,
    session: Session,
    user: Updater,
    metadata: Metadata,
) -> ApiResponse[ValidationRuleResponse]:
    data = await ValidationRuleService(session, user, metadata).set_default(
        entity_id
    )
    return ApiResponse(
        success=True,
        message="Default validation rule updated successfully.",
        data=data,
        errors=None,
    )
