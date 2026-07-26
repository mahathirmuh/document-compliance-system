"""Phase 9 translation-similarity jobs, results, and exports."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.compliance_enums import FindingSeverity
from app.models.similarity_enums import (
    SimilarityCategory,
    SimilarityJobStatus,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.similarity import (
    SectionSimilaritySummaryListResponse,
    SimilarityCancelResponse,
    SimilarityJobListResponse,
    SimilarityJobResponse,
    SimilarityQueuedResponse,
    SimilarityRerunRequest,
    SimilarityRunListResponse,
    SimilarityRunResponse,
    SimilarityStartRequest,
    SimilaritySummaryResponse,
    TranslationSimilarityResultListResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.similarity.similarity_export_service import (
    SimilarityExportService,
    remove_similarity_export_artifact,
)
from app.services.similarity.similarity_job_service import (
    SimilarityJobService,
)
from app.services.similarity.similarity_query_service import (
    SimilarityQueryService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
SimilarityViewer = Annotated[
    User, Depends(require_permissions(Permission.SIMILARITY_VIEW))
]
SimilarityRunner = Annotated[
    User, Depends(require_permissions(Permission.SIMILARITY_RUN))
]
SimilarityRerunner = Annotated[
    User, Depends(require_permissions(Permission.SIMILARITY_RERUN))
]
SimilarityExporter = Annotated[
    User, Depends(require_permissions(Permission.SIMILARITY_EXPORT))
]


def _jobs(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> SimilarityJobService:
    return SimilarityJobService(session, settings, user, metadata)


def _queries(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> SimilarityQueryService:
    return SimilarityQueryService(session, settings, user, metadata)


@router.post(
    "/similarity/jobs",
    response_model=ApiResponse[SimilarityQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_similarity(
    payload: SimilarityStartRequest,
    session: Session,
    settings: Configuration,
    user: SimilarityRunner,
    metadata: Metadata,
) -> ApiResponse[SimilarityQueuedResponse]:
    data = await _jobs(session, settings, user, metadata).start(
        document_file_id=payload.document_file_id,
        compliance_run_id=payload.compliance_run_id,
        language_detection_run_id=payload.language_detection_run_id,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "An equivalent similarity result was reused."
            if data.reused_existing_result
            else "Translation similarity analysis has been queued."
        ),
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/jobs",
    response_model=ApiResponse[SimilarityJobListResponse],
)
async def list_similarity_jobs(
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[
        UUID | None, Query(alias="departmentId")
    ] = None,
    document_id: Annotated[UUID | None, Query(alias="documentId")] = None,
    revision_id: Annotated[UUID | None, Query(alias="revisionId")] = None,
    document_file_id: Annotated[
        UUID | None, Query(alias="documentFileId")
    ] = None,
    compliance_run_id: Annotated[
        UUID | None, Query(alias="complianceRunId")
    ] = None,
    requested_by: Annotated[
        UUID | None, Query(alias="requestedBy")
    ] = None,
    statuses: Annotated[
        list[SimilarityJobStatus] | None, Query(alias="status")
    ] = None,
    requested_from: Annotated[
        datetime | None, Query(alias="requestedFrom")
    ] = None,
    requested_to: Annotated[
        datetime | None, Query(alias="requestedTo")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=100)
    ] = 20,
    sort_by: Annotated[
        Literal["requestedAt", "completedAt", "status", "progress"],
        Query(alias="sortBy"),
    ] = "requestedAt",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sortOrder")
    ] = "desc",
) -> ApiResponse[SimilarityJobListResponse]:
    data = await _jobs(session, settings, user, metadata).list(
        search=search,
        department_id=department_id,
        document_id=document_id,
        revision_id=revision_id,
        document_file_id=document_file_id,
        compliance_run_id=compliance_run_id,
        requested_by=requested_by,
        statuses=statuses,
        requested_from=requested_from,
        requested_to=requested_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Similarity jobs retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/jobs/{job_id}",
    response_model=ApiResponse[SimilarityJobResponse],
)
async def get_similarity_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
) -> ApiResponse[SimilarityJobResponse]:
    data = await _jobs(session, settings, user, metadata).get(job_id)
    return ApiResponse(
        success=True,
        message="Similarity job retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/similarity/jobs/{job_id}/cancel",
    response_model=ApiResponse[SimilarityCancelResponse],
)
async def cancel_similarity_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityRunner,
    metadata: Metadata,
) -> ApiResponse[SimilarityCancelResponse]:
    data = await _jobs(session, settings, user, metadata).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Similarity cancellation has been requested.",
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/runs/{run_id}",
    response_model=ApiResponse[SimilarityRunResponse],
)
async def get_similarity_run(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
) -> ApiResponse[SimilarityRunResponse]:
    data = await _queries(session, settings, user, metadata).get_run(run_id)
    return ApiResponse(
        success=True,
        message="Similarity result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/runs/{run_id}/summary",
    response_model=ApiResponse[SimilaritySummaryResponse],
)
async def get_similarity_summary(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
) -> ApiResponse[SimilaritySummaryResponse]:
    data = await _queries(session, settings, user, metadata).summary(run_id)
    return ApiResponse(
        success=True,
        message="Similarity summary retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/runs/{run_id}/results",
    response_model=ApiResponse[TranslationSimilarityResultListResponse],
)
async def list_similarity_results(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
    section_id: Annotated[
        UUID | None, Query(alias="sectionId")
    ] = None,
    source_language: Annotated[
        Literal["id", "en", "zh"] | None,
        Query(alias="sourceLanguage"),
    ] = None,
    target_language: Annotated[
        Literal["id", "en", "zh"] | None,
        Query(alias="targetLanguage"),
    ] = None,
    similarity_category: Annotated[
        SimilarityCategory | None,
        Query(alias="similarityCategory"),
    ] = None,
    minimum_score: Annotated[
        float | None, Query(alias="minimumScore", ge=0, le=1)
    ] = None,
    maximum_score: Annotated[
        float | None, Query(alias="maximumScore", ge=0, le=1)
    ] = None,
    has_number_mismatch: Annotated[
        bool | None, Query(alias="hasNumberMismatch")
    ] = None,
    has_date_mismatch: Annotated[
        bool | None, Query(alias="hasDateMismatch")
    ] = None,
    has_measurement_mismatch: Annotated[
        bool | None, Query(alias="hasMeasurementMismatch")
    ] = None,
    has_reference_mismatch: Annotated[
        bool | None, Query(alias="hasReferenceMismatch")
    ] = None,
    has_negation_mismatch: Annotated[
        bool | None, Query(alias="hasNegationMismatch")
    ] = None,
    finding_severity: Annotated[
        Literal["CRITICAL", "MAJOR", "MINOR", "INFORMATION", "INFO"]
        | None,
        Query(alias="findingSeverity"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=500)
    ] = 100,
) -> ApiResponse[TranslationSimilarityResultListResponse]:
    data = await _queries(session, settings, user, metadata).list_results(
        run_id,
        section_id=section_id,
        source_language=source_language,
        target_language=target_language,
        similarity_category=similarity_category,
        minimum_score=minimum_score,
        maximum_score=maximum_score,
        has_number_mismatch=has_number_mismatch,
        has_date_mismatch=has_date_mismatch,
        has_measurement_mismatch=has_measurement_mismatch,
        has_reference_mismatch=has_reference_mismatch,
        has_negation_mismatch=has_negation_mismatch,
        finding_severity=(
            FindingSeverity.INFORMATION
            if finding_severity == "INFO"
            else (
                FindingSeverity(finding_severity)
                if finding_severity is not None
                else None
            )
        ),
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Similarity pair results retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/similarity/runs/{run_id}/sections",
    response_model=ApiResponse[SectionSimilaritySummaryListResponse],
)
async def list_similarity_sections(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=500)
    ] = 100,
) -> ApiResponse[SectionSimilaritySummaryListResponse]:
    data = await _queries(session, settings, user, metadata).list_sections(
        run_id, page=page, page_size=page_size
    )
    return ApiResponse(
        success=True,
        message="Section similarity summaries retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/similarity/runs/{run_id}/export")
async def export_similarity_result(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: SimilarityExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "xlsx"], Query(alias="format")
    ] = "json",
) -> FileResponse:
    artifact = await SimilarityExportService(
        session, settings, user, metadata
    ).export(run_id, export_format=export_format)
    background_tasks.add_task(
        remove_similarity_export_artifact, Path(artifact.path)
    )
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        filename=artifact.filename,
        background=background_tasks,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.post(
    "/similarity/runs/{run_id}/rerun",
    response_model=ApiResponse[SimilarityQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def rerun_similarity(
    run_id: UUID,
    payload: SimilarityRerunRequest,
    session: Session,
    settings: Configuration,
    user: SimilarityRerunner,
    metadata: Metadata,
) -> ApiResponse[SimilarityQueuedResponse]:
    data = await _jobs(session, settings, user, metadata).rerun(
        run_id, reason=payload.reason
    )
    return ApiResponse(
        success=True,
        message="Similarity reanalysis has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/similarity",
    response_model=ApiResponse[SimilarityRunResponse],
)
async def get_latest_file_similarity(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
) -> ApiResponse[SimilarityRunResponse]:
    data = await _queries(
        session, settings, user, metadata
    ).latest_for_file(file_id)
    return ApiResponse(
        success=True,
        message="Latest similarity result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/similarity-history",
    response_model=ApiResponse[SimilarityRunListResponse],
)
async def get_file_similarity_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: SimilarityViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=100)
    ] = 20,
) -> ApiResponse[SimilarityRunListResponse]:
    data = await _queries(
        session, settings, user, metadata
    ).history_for_file(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Similarity history retrieved successfully.",
        data=data,
        errors=None,
    )
