"""Phase 7 language detection jobs, results, history, and exports."""

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
from app.models.language_block_result import (
    LanguageCode,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.models.language_detection_job import LanguageDetectionJobStatus
from app.models.user import User
from app.schemas.common import ApiResponse, PaginationData
from app.schemas.language_detection import (
    LanguageBlockResultListResponse,
    LanguageContainerSummaryListResponse,
    LanguageDetectionCancelResponse,
    LanguageDetectionDocumentListResponse,
    LanguageDetectionDocumentStatus,
    LanguageDetectionHistoryItem,
    LanguageDetectionJobListResponse,
    LanguageDetectionJobResponse,
    LanguageDetectionQueuedResponse,
    LanguageDetectionRunResponse,
    LanguageDetectionStartRequest,
    LanguageRedetectRequest,
    LanguageSummaryResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import document_error
from app.services.language.language_detection_document_service import (
    LanguageDetectionDocumentService,
)
from app.services.language.language_detection_job_service import (
    LanguageDetectionJobService,
    LanguageResultService,
)
from app.services.language.language_export_service import (
    LanguageExportService,
    remove_language_export_artifact,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
LanguageViewer = Annotated[
    User,
    Depends(
        require_permissions(Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS)
    ),
]
LanguageDetector = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_DETECT_LANGUAGE)),
]
LanguageRedetector = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_REDETECT_LANGUAGE)),
]
LanguageExporter = Annotated[
    User,
    Depends(
        require_permissions(Permission.DOCUMENTS_EXPORT_LANGUAGE_RESULTS)
    ),
]


def _job_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> LanguageDetectionJobService:
    return LanguageDetectionJobService(session, settings, user, metadata)


def _result_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> LanguageResultService:
    return LanguageResultService(session, settings, user, metadata)


@router.get(
    "/language-detection/documents",
    response_model=ApiResponse[LanguageDetectionDocumentListResponse],
)
async def list_language_detection_documents(
    session: Session,
    user: LanguageViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_status: Annotated[
        LanguageDetectionDocumentStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal["documentCode", "filename", "uploadedAt"],
        Query(alias="sortBy"),
    ] = "documentCode",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "asc",
) -> ApiResponse[LanguageDetectionDocumentListResponse]:
    data = await LanguageDetectionDocumentService(
        session,
        user,
        metadata,
    ).list(
        search=search,
        department_id=department_id,
        status=document_status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Language-detection documents retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/language-detection/jobs",
    response_model=ApiResponse[LanguageDetectionQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_language_detection(
    payload: LanguageDetectionStartRequest,
    session: Session,
    settings: Configuration,
    user: LanguageDetector,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).start(
        document_file_id=payload.document_file_id,
        extraction_run_id=payload.extraction_run_id,
        ocr_run_id=payload.ocr_run_id,
        force=payload.force,
    )
    return ApiResponse(
        success=True,
        message=(
            "An existing language result was reused."
            if data.reused_existing_result
            else "Language detection has been queued."
        ),
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/jobs",
    response_model=ApiResponse[LanguageDetectionJobListResponse],
)
async def list_language_detection_jobs(
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    department_id: Annotated[
        UUID | None,
        Query(alias="departmentId"),
    ] = None,
    document_id: Annotated[
        UUID | None,
        Query(alias="documentId"),
    ] = None,
    revision_id: Annotated[
        UUID | None,
        Query(alias="revisionId"),
    ] = None,
    document_file_id: Annotated[
        UUID | None,
        Query(alias="documentFileId"),
    ] = None,
    statuses: Annotated[
        list[LanguageDetectionJobStatus] | None,
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
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal["requestedAt", "completedAt", "status", "progress"],
        Query(alias="sortBy"),
    ] = "requestedAt",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "desc",
) -> ApiResponse[LanguageDetectionJobListResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).list(
        search=search,
        department_id=department_id,
        document_id=document_id,
        revision_id=revision_id,
        document_file_id=document_file_id,
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
        message="Language detection jobs retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/jobs/{job_id}",
    response_model=ApiResponse[LanguageDetectionJobResponse],
)
async def get_language_detection_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionJobResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).get(job_id)
    return ApiResponse(
        success=True,
        message="Language detection job retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/language-detection/jobs/{job_id}/cancel",
    response_model=ApiResponse[LanguageDetectionCancelResponse],
)
async def cancel_language_detection_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageDetector,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionCancelResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="Language detection cancellation has been requested.",
        data=data,
        errors=None,
    )


@router.post(
    "/language-detection/runs/{run_id}/redetect",
    response_model=ApiResponse[LanguageDetectionQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def redetect_language(
    run_id: UUID,
    payload: LanguageRedetectRequest,
    session: Session,
    settings: Configuration,
    user: LanguageRedetector,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).redetect(run_id, reason=payload.reason)
    return ApiResponse(
        success=True,
        message="Language re-detection has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/runs/{run_id}",
    response_model=ApiResponse[LanguageDetectionRunResponse],
)
async def get_language_detection_run(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionRunResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).get_run(run_id)
    return ApiResponse(
        success=True,
        message="Language detection result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/runs/{run_id}/summary",
    response_model=ApiResponse[LanguageSummaryResponse],
)
async def get_language_detection_summary(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
) -> ApiResponse[LanguageSummaryResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).summary(run_id)
    return ApiResponse(
        success=True,
        message="Language presence and preliminary coverage retrieved.",
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/runs/{run_id}/blocks",
    response_model=ApiResponse[LanguageBlockResultListResponse],
)
async def list_language_block_results(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
    language_code: Annotated[
        LanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    source_type: Annotated[
        LanguageSourceType | None,
        Query(alias="sourceType"),
    ] = None,
    container_id: Annotated[
        UUID | None,
        Query(alias="containerId"),
    ] = None,
    minimum_confidence: Annotated[
        float | None,
        Query(alias="minimumConfidence", ge=0, le=1),
    ] = None,
    maximum_confidence: Annotated[
        float | None,
        Query(alias="maximumConfidence", ge=0, le=1),
    ] = None,
    is_mixed: Annotated[
        bool | None,
        Query(alias="isMixed"),
    ] = None,
    eligibility_status: Annotated[
        LanguageEligibilityStatus | None,
        Query(alias="eligibilityStatus"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[LanguageBlockResultListResponse]:
    if (
        minimum_confidence is not None
        and maximum_confidence is not None
        and minimum_confidence > maximum_confidence
    ):
        raise document_error(
            "minimumConfidence must not exceed maximumConfidence.",
            field="minimumConfidence",
            title="Language block filters are invalid.",
        )
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).list_blocks(
        run_id,
        language_code=language_code,
        source_type=source_type,
        container_id=container_id,
        minimum_confidence=minimum_confidence,
        maximum_confidence=maximum_confidence,
        is_mixed=is_mixed,
        eligibility_status=eligibility_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Language block results retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/language-detection/runs/{run_id}/containers",
    response_model=ApiResponse[LanguageContainerSummaryListResponse],
)
async def list_language_container_summaries(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[LanguageContainerSummaryListResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).list_containers(run_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Language container summaries retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/language-detection/runs/{run_id}/export")
async def export_language_detection(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: LanguageExporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "xlsx"],
        Query(alias="format"),
    ] = "json",
) -> FileResponse:
    artifact = await LanguageExportService(
        session,
        settings,
        user,
        metadata,
    ).export(run_id, export_format=export_format)
    background_tasks.add_task(
        remove_language_export_artifact,
        Path(artifact.path),
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


@router.get(
    "/document-files/{file_id}/language-detection",
    response_model=ApiResponse[LanguageDetectionRunResponse],
)
async def get_latest_file_language_detection(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
) -> ApiResponse[LanguageDetectionRunResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).latest_for_file(file_id)
    return ApiResponse(
        success=True,
        message="Latest language detection result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/language-detection-history",
    response_model=(
        ApiResponse[PaginationData[LanguageDetectionHistoryItem]]
    ),
)
async def get_file_language_detection_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: LanguageViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[PaginationData[LanguageDetectionHistoryItem]]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).history_for_file(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Language detection history retrieved successfully.",
        data=data,
        errors=None,
    )
