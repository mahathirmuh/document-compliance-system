"""Authenticated, department-scoped OCR queue and result endpoints."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, cast
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
from app.models.ocr_job import OCRJobStatus, OCRLanguageProfile
from app.models.ocr_page_result import OCRPageStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.ocr import (
    OCRBlockListResponse,
    OCRCancelResponse,
    OCRJobListResponse,
    OCRJobResponse,
    OCRPageDetailResponse,
    OCRPageListResponse,
    OCRQueuedResponse,
    OCRReprocessRequest,
    OCRRunHistoryResponse,
    OCRRunResponse,
    OCRStartRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.ocr.ocr_export_service import (
    OCRExportService,
    remove_ocr_export_artifact,
)
from app.services.ocr.ocr_job_service import OCRJobService
from app.services.ocr.ocr_result_service import OCRResultService

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
OCRStarter = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_OCR)),
]
OCRViewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW_OCR_RESULTS)),
]
OCRHistoryViewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW_OCR_HISTORY)),
]
OCRCanceller = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_CANCEL_OCR)),
]
OCRReprocessor = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_REOCR)),
]


def _job_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> OCRJobService:
    return OCRJobService(session, settings, user, metadata)


def _result_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> OCRResultService:
    return OCRResultService(session, settings, user, metadata)


@router.post(
    "/ocr/jobs",
    response_model=ApiResponse[OCRQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_ocr_job(
    payload: OCRStartRequest,
    session: Session,
    settings: Configuration,
    user: OCRStarter,
    metadata: Metadata,
) -> ApiResponse[OCRQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).start(payload)
    return ApiResponse(
        success=True,
        message="OCR job has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/ocr/jobs",
    response_model=ApiResponse[OCRJobListResponse],
)
async def list_ocr_jobs(
    session: Session,
    settings: Configuration,
    user: OCRViewer,
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
        list[OCRJobStatus] | None,
        Query(alias="status"),
    ] = None,
    language_profile: Annotated[
        OCRLanguageProfile | None,
        Query(alias="languageProfile"),
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
) -> ApiResponse[OCRJobListResponse]:
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
        language_profile=language_profile,
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
        message="OCR jobs retrieved successfully.",
        data=cast(OCRJobListResponse, data),
        errors=None,
    )


@router.get(
    "/ocr/jobs/{job_id}",
    response_model=ApiResponse[OCRJobResponse],
)
async def get_ocr_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
) -> ApiResponse[OCRJobResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).get(job_id)
    return ApiResponse(
        success=True,
        message="OCR job retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/ocr/jobs/{job_id}/cancel",
    response_model=ApiResponse[OCRCancelResponse],
)
async def cancel_ocr_job(
    job_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRCanceller,
    metadata: Metadata,
) -> ApiResponse[OCRCancelResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).cancel(job_id)
    return ApiResponse(
        success=True,
        message="OCR cancellation has been requested.",
        data=data,
        errors=None,
    )


@router.get(
    "/ocr/runs/{run_id}",
    response_model=ApiResponse[OCRRunResponse],
)
async def get_ocr_run(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
) -> ApiResponse[OCRRunResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).get_run(run_id)
    return ApiResponse(
        success=True,
        message="OCR result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/ocr/runs/{run_id}/pages",
    response_model=ApiResponse[OCRPageListResponse],
)
async def list_ocr_pages(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
    statuses: Annotated[
        list[OCRPageStatus] | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 20,
) -> ApiResponse[OCRPageListResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).list_pages(
        run_id,
        statuses=statuses,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="OCR page results retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/ocr/runs/{run_id}/pages/{page_number}",
    response_model=ApiResponse[OCRPageDetailResponse],
)
async def get_ocr_page(
    run_id: UUID,
    page_number: int,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
) -> ApiResponse[OCRPageDetailResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).get_page(run_id, page_number)
    return ApiResponse(
        success=True,
        message="OCR page result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/ocr/runs/{run_id}/blocks",
    response_model=ApiResponse[OCRBlockListResponse],
)
async def list_ocr_blocks(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
    page_number: Annotated[
        int | None,
        Query(alias="pageNumber", ge=1),
    ] = None,
    minimum_confidence: Annotated[
        float | None,
        Query(alias="minimumConfidence", ge=0, le=1),
    ] = None,
    maximum_confidence: Annotated[
        float | None,
        Query(alias="maximumConfidence", ge=0, le=1),
    ] = None,
    search: Annotated[
        str | None,
        Query(min_length=1, max_length=200),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[OCRBlockListResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).list_blocks(
        run_id,
        page_number=page_number,
        minimum_confidence=minimum_confidence,
        maximum_confidence=maximum_confidence,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="OCR blocks retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get("/ocr/runs/{run_id}/export")
async def export_ocr_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "txt"],
        Query(alias="format"),
    ] = "json",
) -> FileResponse:
    artifact = await OCRExportService(
        session,
        settings,
        user,
        metadata,
    ).export(run_id, export_format=export_format)
    background_tasks.add_task(
        remove_ocr_export_artifact,
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


@router.post(
    "/ocr/runs/{run_id}/reocr",
    response_model=ApiResponse[OCRQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_ocr_run(
    run_id: UUID,
    payload: OCRReprocessRequest,
    session: Session,
    settings: Configuration,
    user: OCRReprocessor,
    metadata: Metadata,
) -> ApiResponse[OCRQueuedResponse]:
    data = await _job_service(
        session,
        settings,
        user,
        metadata,
    ).reocr(run_id, payload)
    return ApiResponse(
        success=True,
        message="Re-OCR job has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/ocr",
    response_model=ApiResponse[OCRRunResponse],
)
async def get_latest_file_ocr(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRViewer,
    metadata: Metadata,
) -> ApiResponse[OCRRunResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).latest_for_file(file_id)
    return ApiResponse(
        success=True,
        message="Latest OCR result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/ocr-history",
    response_model=ApiResponse[OCRRunHistoryResponse],
)
async def get_file_ocr_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: OCRHistoryViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[OCRRunHistoryResponse]:
    data = await _result_service(
        session,
        settings,
        user,
        metadata,
    ).history_for_file(
        file_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="OCR history retrieved successfully.",
        data=data,
        errors=None,
    )
