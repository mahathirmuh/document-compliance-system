"""Authenticated extraction queue and job lifecycle endpoints."""

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_active_user,
    get_request_metadata,
)
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.extraction_job import ExtractionJobStatus
from app.models.extraction_run import ExtractorType
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.extraction_job import (
    ExtractionCancelResponse,
    ExtractionJobDetailResponse,
    ExtractionJobListResponse,
    ExtractionQueuedResponse,
    ExtractionRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.extraction.extraction_job_service import (
    ExtractionJobService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]


def _service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> ExtractionJobService:
    return ExtractionJobService(session, settings, user, metadata)


@router.post(
    "",
    response_model=ApiResponse[ExtractionQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_extraction(
    payload: ExtractionRequest,
    session: Session,
    settings: Configuration,
    user: ActiveUser,
    metadata: Metadata,
) -> ApiResponse[ExtractionQueuedResponse]:
    data = await _service(session, settings, user, metadata).start(
        payload.document_file_id,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "An existing extraction result was reused."
            if data.reused_existing_result
            else "Document extraction has been queued."
        ),
        data=data,
        errors=None,
    )


@router.get(
    "",
    response_model=ApiResponse[ExtractionJobListResponse],
)
async def list_extractions(
    session: Session,
    settings: Configuration,
    user: ActiveUser,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[UUID | None, Query(alias="departmentId")] = None,
    document_id: Annotated[UUID | None, Query(alias="documentId")] = None,
    revision_id: Annotated[UUID | None, Query(alias="revisionId")] = None,
    document_file_id: Annotated[
        UUID | None,
        Query(alias="documentFileId"),
    ] = None,
    extractor_type: Annotated[
        ExtractorType | None,
        Query(alias="extractorType"),
    ] = None,
    statuses: Annotated[
        list[ExtractionJobStatus] | None,
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
    sort_by: Annotated[
        Literal["requestedAt", "completedAt", "status", "progress"],
        Query(alias="sortBy"),
    ] = "requestedAt",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> ApiResponse[ExtractionJobListResponse]:
    data = await _service(session, settings, user, metadata).list(
        search=search,
        department_id=department_id,
        document_id=document_id,
        revision_id=revision_id,
        document_file_id=document_file_id,
        extractor_type=extractor_type,
        statuses=statuses,
        requested_by=requested_by,
        requested_from=requested_from,
        requested_to=requested_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Extraction jobs retrieved successfully.",
        data=cast(ExtractionJobListResponse, data),
        errors=None,
    )


@router.get(
    "/{job_id}",
    response_model=ApiResponse[ExtractionJobDetailResponse],
)
async def get_extraction(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: ActiveUser,
    metadata: Metadata,
) -> ApiResponse[ExtractionJobDetailResponse]:
    data = await _service(session, settings, user, metadata).get(job_id)
    return ApiResponse(
        success=True,
        message="Extraction job retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=ApiResponse[ExtractionCancelResponse],
)
async def cancel_extraction(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: ActiveUser,
    metadata: Metadata,
) -> ApiResponse[ExtractionCancelResponse]:
    data = await _service(session, settings, user, metadata).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Extraction cancellation has been requested.",
        data=data,
        errors=None,
    )
