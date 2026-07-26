"""Phase 9 revision comparison jobs, results, and private exports."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.revision_change import (
    RevisionChangeType,
    RevisionEntityType,
)
from app.models.revision_comparison_job import RevisionComparisonJobStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.revision_comparison import (
    RevisionChangeListResponse,
    RevisionComparisonHistoryResponse,
    RevisionComparisonJobListResponse,
    RevisionComparisonJobResponse,
    RevisionComparisonQueuedResponse,
    RevisionComparisonResponse,
    RevisionComparisonStartRequest,
    RevisionComparisonSummaryResponse,
    RevisionFindingChangesResponse,
    RevisionLanguageChangesResponse,
    RevisionSectionChangesResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.revision_comparison.revision_comparison_service import (
    RevisionComparisonJobService,
    RevisionComparisonQueryService,
)
from app.services.revision_comparison.revision_export_service import (
    RevisionExportService,
)

router = APIRouter(tags=["revision-comparisons"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
RevisionViewer = Annotated[
    User,
    Depends(require_permissions(Permission.REVISION_COMPARISON_VIEW)),
]
RevisionRunner = Annotated[
    User,
    Depends(require_permissions(Permission.REVISION_COMPARISON_RUN)),
]
RevisionExporter = Annotated[
    User,
    Depends(require_permissions(Permission.REVISION_COMPARISON_EXPORT)),
]


@router.post(
    "/revision-comparisons/jobs",
    response_model=ApiResponse[RevisionComparisonQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_revision_comparison(
    payload: RevisionComparisonStartRequest,
    session: Session,
    settings: Configuration,
    user: RevisionRunner,
    metadata: Metadata,
) -> ApiResponse[RevisionComparisonQueuedResponse]:
    result = await RevisionComparisonJobService(
        session, settings, user, metadata
    ).start(
        document_id=payload.document_id,
        base_revision_id=payload.base_revision_id,
        target_revision_id=payload.target_revision_id,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "An equivalent revision comparison was reused."
            if result.reused_existing_result
            else "Revision comparison has been queued."
        ),
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/jobs",
    response_model=ApiResponse[RevisionComparisonJobListResponse],
)
async def list_revision_comparison_jobs(
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
    document_id: Annotated[
        UUID | None, Query(alias="documentId")
    ] = None,
    statuses: Annotated[
        list[RevisionComparisonJobStatus] | None, Query(alias="status")
    ] = None,
    requested_from: Annotated[
        datetime | None, Query(alias="requestedFrom")
    ] = None,
    requested_to: Annotated[
        datetime | None, Query(alias="requestedTo")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[RevisionComparisonJobListResponse]:
    result = await RevisionComparisonJobService(
        session, settings, user, metadata
    ).list(
        document_id=document_id,
        statuses=statuses,
        requested_from=requested_from,
        requested_to=requested_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Revision comparison jobs retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/jobs/{job_id}",
    response_model=ApiResponse[RevisionComparisonJobResponse],
)
async def get_revision_comparison_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionComparisonJobResponse]:
    result = await RevisionComparisonJobService(
        session, settings, user, metadata
    ).get(job_id)
    return ApiResponse(
        success=True,
        message="Revision comparison job retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/revision-comparisons/jobs/{job_id}/cancel",
    response_model=ApiResponse[RevisionComparisonJobResponse],
)
async def cancel_revision_comparison_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionRunner,
    metadata: Metadata,
) -> ApiResponse[RevisionComparisonJobResponse]:
    result = await RevisionComparisonJobService(
        session, settings, user, metadata
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Revision comparison cancellation requested.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}",
    response_model=ApiResponse[RevisionComparisonResponse],
)
async def get_revision_comparison(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionComparisonResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).get_comparison(comparison_id)
    return ApiResponse(
        success=True,
        message="Revision comparison retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}/summary",
    response_model=ApiResponse[RevisionComparisonSummaryResponse],
)
async def get_revision_comparison_summary(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionComparisonSummaryResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).summary(comparison_id)
    return ApiResponse(
        success=True,
        message="Revision comparison summary retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}/changes",
    response_model=ApiResponse[RevisionChangeListResponse],
)
async def list_revision_changes(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
    change_types: Annotated[
        list[RevisionChangeType] | None, Query(alias="changeType")
    ] = None,
    entity_types: Annotated[
        list[RevisionEntityType] | None, Query(alias="entityType")
    ] = None,
    language_code: Annotated[
        str | None, Query(alias="languageCode", max_length=20)
    ] = None,
    section_id: Annotated[
        UUID | None, Query(alias="sectionId")
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=500)
    ] = 100,
) -> ApiResponse[RevisionChangeListResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).list_changes(
        comparison_id,
        change_types=change_types,
        entity_types=entity_types,
        language_code=language_code,
        section_id=section_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Revision changes retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}/sections",
    response_model=ApiResponse[RevisionSectionChangesResponse],
)
async def get_revision_section_changes(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionSectionChangesResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).sections(comparison_id)
    return ApiResponse(
        success=True,
        message="Revision section changes retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}/languages",
    response_model=ApiResponse[RevisionLanguageChangesResponse],
)
async def get_revision_language_changes(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionLanguageChangesResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).languages(comparison_id)
    return ApiResponse(
        success=True,
        message="Revision language changes retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/revision-comparisons/{comparison_id}/findings",
    response_model=ApiResponse[RevisionFindingChangesResponse],
)
async def get_revision_finding_changes(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
) -> ApiResponse[RevisionFindingChangesResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).findings(comparison_id)
    return ApiResponse(
        success=True,
        message="Revision finding changes retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get("/revision-comparisons/{comparison_id}/export")
async def export_revision_comparison(
    comparison_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionExporter,
    metadata: Metadata,
    export_format: Annotated[
        str, Query(alias="format", pattern="^(json|xlsx|pdf)$")
    ] = "json",
) -> Response:
    artifact = await RevisionExportService(
        session, settings, user, metadata
    ).export(comparison_id, export_format=export_format)
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{artifact.filename}"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/documents/{document_id}/revision-comparisons",
    response_model=ApiResponse[RevisionComparisonHistoryResponse],
)
async def list_document_revision_comparisons(
    document_id: UUID,
    session: Session,
    settings: Configuration,
    user: RevisionViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[RevisionComparisonHistoryResponse]:
    result = await RevisionComparisonQueryService(
        session, settings, user, metadata
    ).history(document_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Document revision comparisons retrieved successfully.",
        data=result,
        errors=None,
    )
