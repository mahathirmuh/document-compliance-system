"""Extraction result, content, history, search, and export endpoints."""

from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.extracted_block import ExtractedBlockType
from app.models.extracted_container import ExtractedContainerType
from app.models.language_block_result import LanguageCode
from app.models.user import User
from app.schemas.common import ApiResponse, PaginationData
from app.schemas.extracted_content import (
    ExtractedBlockListResponse,
    ExtractedContainerListResponse,
    ExtractedContentSearchResponse,
    ExtractedContentSource,
    ExtractedTableListResponse,
)
from app.schemas.extraction_job import (
    ExtractionQueuedResponse,
    ReExtractionRequest,
)
from app.schemas.extraction_run import (
    ExtractionRunHistoryItem,
    ExtractionRunResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.extraction.extraction_content_service import (
    ExtractionContentService,
)
from app.services.extraction.extraction_export_service import (
    ExtractionExportService,
    remove_export_artifact,
)
from app.services.extraction.extraction_job_service import (
    ExtractionJobService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
ContentViewer = Annotated[
    User,
    Depends(
        require_permissions(Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT)
    ),
]
HistoryViewer = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY)),
]
ReExtractor = Annotated[
    User,
    Depends(require_permissions(Permission.DOCUMENTS_REEXTRACT)),
]
Exporter = Annotated[
    User,
    Depends(
        require_permissions(Permission.DOCUMENTS_EXPORT_EXTRACTED_CONTENT)
    ),
]


def _content_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> ExtractionContentService:
    return ExtractionContentService(session, settings, user, metadata)


@router.post(
    "/document-files/{file_id}/reextract",
    response_model=ApiResponse[ExtractionQueuedResponse],
    status_code=202,
)
async def reextract_document_file(
    file_id: UUID,
    payload: ReExtractionRequest,
    session: Session,
    settings: Configuration,
    user: ReExtractor,
    metadata: Metadata,
) -> ApiResponse[ExtractionQueuedResponse]:
    data = await ExtractionJobService(
        session,
        settings,
        user,
        metadata,
    ).reextract(file_id, reason=payload.reason)
    return ApiResponse(
        success=True,
        message="Document re-extraction has been queued.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/extraction",
    response_model=ApiResponse[ExtractionRunResponse],
)
async def get_latest_file_extraction(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
) -> ApiResponse[ExtractionRunResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).latest_for_file(file_id)
    return ApiResponse(
        success=True,
        message="Latest extraction result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/document-files/{file_id}/extraction-history",
    response_model=ApiResponse[PaginationData[ExtractionRunHistoryItem]],
)
async def get_file_extraction_history(
    file_id: UUID,
    session: Session,
    settings: Configuration,
    user: HistoryViewer,
    metadata: Metadata,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[PaginationData[ExtractionRunHistoryItem]]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).history_for_file(file_id, page=page, page_size=page_size)
    return ApiResponse(
        success=True,
        message="Extraction history retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/extraction-runs/{run_id}",
    response_model=ApiResponse[ExtractionRunResponse],
)
async def get_extraction_run(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
) -> ApiResponse[ExtractionRunResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).get_run(run_id)
    return ApiResponse(
        success=True,
        message="Extraction result retrieved successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/extraction-runs/{run_id}/containers",
    response_model=ApiResponse[ExtractedContainerListResponse],
)
async def list_extracted_containers(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
    container_type: Annotated[
        ExtractedContainerType | None,
        Query(alias="containerType"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
) -> ApiResponse[ExtractedContainerListResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).list_containers(
        run_id,
        container_type=container_type,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Extracted containers retrieved successfully.",
        data=cast(ExtractedContainerListResponse, data),
        errors=None,
    )


@router.get(
    "/extraction-runs/{run_id}/blocks",
    response_model=ApiResponse[ExtractedBlockListResponse],
)
async def list_extracted_blocks(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
    container_id: Annotated[
        UUID | None,
        Query(alias="containerId"),
    ] = None,
    block_type: Annotated[
        ExtractedBlockType | None,
        Query(alias="blockType"),
    ] = None,
    content_source: Annotated[
        ExtractedContentSource | None,
        Query(alias="contentSource"),
    ] = None,
    language_code: Annotated[
        LanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 100,
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(alias="sortOrder"),
    ] = "asc",
) -> ApiResponse[ExtractedBlockListResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).list_blocks(
        run_id,
        container_id=container_id,
        block_type=block_type,
        content_source=content_source,
        language_code=language_code,
        search=search,
        page=page,
        page_size=page_size,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Extracted blocks retrieved successfully.",
        data=cast(ExtractedBlockListResponse, data),
        errors=None,
    )


@router.get(
    "/extraction-runs/{run_id}/tables",
    response_model=ApiResponse[ExtractedTableListResponse],
)
async def list_extracted_tables(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
    container_id: Annotated[
        UUID | None,
        Query(alias="containerId"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    include_cells: Annotated[
        bool,
        Query(alias="includeCells"),
    ] = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[ExtractedTableListResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).list_tables(
        run_id,
        container_id=container_id,
        search=search,
        include_cells=include_cells,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Extracted tables retrieved successfully.",
        data=cast(ExtractedTableListResponse, data),
        errors=None,
    )


@router.get(
    "/extraction-runs/{run_id}/search",
    response_model=ApiResponse[ExtractedContentSearchResponse],
)
async def search_extracted_content(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    user: ContentViewer,
    metadata: Metadata,
    query: Annotated[str, Query(alias="q", min_length=2, max_length=200)],
) -> ApiResponse[ExtractedContentSearchResponse]:
    data = await _content_service(
        session,
        settings,
        user,
        metadata,
    ).search(run_id, query=query)
    return ApiResponse(
        success=True,
        message="Extracted content search completed successfully.",
        data=data,
        errors=None,
    )


@router.get("/extraction-runs/{run_id}/export")
async def export_extracted_content(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session,
    settings: Configuration,
    user: Exporter,
    metadata: Metadata,
    export_format: Annotated[
        Literal["json", "txt"],
        Query(alias="format"),
    ] = "json",
) -> FileResponse:
    artifact = await ExtractionExportService(
        session,
        settings,
        user,
        metadata,
    ).export(run_id, export_format=export_format)
    background_tasks.add_task(
        remove_export_artifact,
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
