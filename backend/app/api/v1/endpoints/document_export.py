"""Filtered Document Register XLSX export endpoint."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.document import DocumentFilter
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.document_export_service import (
    XLSX_CONTENT_TYPE,
    DocumentExportService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
Exporter = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_EXPORT)),
]


@router.get("/export")
async def export_document_register(
    session: Session,
    settings: Configuration,
    user: Exporter,
    metadata: Metadata,
    search: str | None = None,
    base_document_code: Annotated[
        str | None,
        Query(alias="baseDocumentCode", min_length=1, max_length=255),
    ] = None,
    department_id: Annotated[
        UUID | None, Query(alias="departmentId")
    ] = None,
    section_id: Annotated[UUID | None, Query(alias="sectionId")] = None,
    document_type_id: Annotated[
        UUID | None, Query(alias="documentTypeId")
    ] = None,
    document_status_id: Annotated[
        UUID | None, Query(alias="documentStatusId")
    ] = None,
    validation_rule_id: Annotated[
        UUID | None, Query(alias="validationRuleId")
    ] = None,
    revision_code: Annotated[
        str | None, Query(alias="revisionCode")
    ] = None,
    company_code: Annotated[str | None, Query(alias="companyCode")] = None,
    is_archived: Annotated[bool, Query(alias="isArchived")] = False,
    has_sharepoint_url: Annotated[
        bool | None, Query(alias="hasSharePointUrl")
    ] = None,
    created_by: Annotated[UUID | None, Query(alias="createdBy")] = None,
    created_from: Annotated[
        date | None, Query(alias="createdFrom")
    ] = None,
    created_to: Annotated[date | None, Query(alias="createdTo")] = None,
    effective_from: Annotated[
        date | None, Query(alias="effectiveFrom")
    ] = None,
    effective_to: Annotated[
        date | None, Query(alias="effectiveTo")
    ] = None,
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
        Literal["asc", "desc"], Query(alias="sortOrder")
    ] = "desc",
) -> Response:
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
        page=1,
        page_size=100,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    content, filename = await DocumentExportService(
        session, settings, user, metadata
    ).export(filters)
    return Response(
        content=content,
        media_type=XLSX_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
