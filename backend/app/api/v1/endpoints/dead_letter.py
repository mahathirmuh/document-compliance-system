"""Administrative dead-letter job inspection and recovery endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.database.session import get_db_session
from app.models.dead_letter_job import DeadLetterStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.dead_letter import (
    DeadLetterActionRequest,
    DeadLetterListResponse,
    DeadLetterMutationResponse,
)
from app.services.maintenance.dead_letter_service import (
    DeadLetterRetryPublisher,
    DeadLetterService,
)

router = APIRouter(prefix="/admin", tags=["Background Job Administration"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
JobManager = Annotated[
    User,
    Depends(require_permissions("background_jobs:manage")),
]


def get_dead_letter_retry_publisher() -> DeadLetterRetryPublisher | None:
    """Override at application composition with the bounded Celery publisher."""

    return None


RetryPublisher = Annotated[
    DeadLetterRetryPublisher | None,
    Depends(get_dead_letter_retry_publisher),
]


@router.get(
    "/dead-letter-jobs",
    response_model=ApiResponse[DeadLetterListResponse],
)
async def list_dead_letter_jobs(
    session: Session,
    user: JobManager,
    job_status: Annotated[
        DeadLetterStatus | None,
        Query(alias="status"),
    ] = None,
    task_name: Annotated[str | None, Query(alias="taskName")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[DeadLetterListResponse]:
    result = await DeadLetterService(session).list(
        status=job_status,
        task_name=task_name,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Dead-letter jobs retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/dead-letter-jobs/{job_id}/retry",
    response_model=ApiResponse[DeadLetterMutationResponse],
)
async def retry_dead_letter_job(
    job_id: UUID,
    session: Session,
    user: JobManager,
    publisher: RetryPublisher,
) -> ApiResponse[DeadLetterMutationResponse]:
    result = await DeadLetterService(
        session,
        publisher=publisher,
    ).retry(job_id)
    return ApiResponse(
        success=True,
        message="Dead-letter job retry queued.",
        data=result,
        errors=None,
    )


@router.post(
    "/dead-letter-jobs/{job_id}/dismiss",
    response_model=ApiResponse[DeadLetterMutationResponse],
)
async def dismiss_dead_letter_job(
    job_id: UUID,
    payload: DeadLetterActionRequest,
    session: Session,
    user: JobManager,
) -> ApiResponse[DeadLetterMutationResponse]:
    result = await DeadLetterService(session).dismiss(
        job_id,
        actor_id=user.id,
        reason=payload.reason,
    )
    return ApiResponse(
        success=True,
        message="Dead-letter job dismissed.",
        data=result,
        errors=None,
    )
