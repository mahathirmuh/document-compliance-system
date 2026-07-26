"""Retention policy administration and dry-run-first execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.database.session import get_db_session
from app.models.data_retention_policy import RetentionEntityType
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.retention import (
    RetentionPolicyCreateRequest,
    RetentionPolicyListResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpdateRequest,
    RetentionRunRequest,
    RetentionRunResponse,
)
from app.services.retention.contracts import RetentionEntityHandler
from app.services.retention.retention_policy_service import (
    RetentionPolicyService,
)
from app.services.retention.retention_service import RetentionService

router = APIRouter(prefix="/admin", tags=["Retention Administration"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
RetentionManager = Annotated[
    User,
    Depends(require_permissions("retention_policies:manage")),
]


def get_retention_handlers() -> Mapping[
    RetentionEntityType,
    RetentionEntityHandler,
]:
    """Override with entity-specific cleanup handlers at app composition."""

    return {}


RetentionHandlers = Annotated[
    Mapping[RetentionEntityType, RetentionEntityHandler],
    Depends(get_retention_handlers),
]


@router.get(
    "/retention-policies",
    response_model=ApiResponse[RetentionPolicyListResponse],
)
async def list_retention_policies(
    session: Session,
    user: RetentionManager,
    entity_type: Annotated[
        RetentionEntityType | None,
        Query(alias="entityType"),
    ] = None,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[RetentionPolicyListResponse]:
    result = await RetentionPolicyService(
        session,
        actor_id=user.id,
    ).list(
        entity_type=entity_type,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Retention policies retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/retention-policies",
    response_model=ApiResponse[RetentionPolicyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_retention_policy(
    payload: RetentionPolicyCreateRequest,
    session: Session,
    user: RetentionManager,
) -> ApiResponse[RetentionPolicyResponse]:
    result = await RetentionPolicyService(
        session,
        actor_id=user.id,
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Retention policy created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/retention-policies/{policy_id}",
    response_model=ApiResponse[RetentionPolicyResponse],
)
async def update_retention_policy(
    policy_id: UUID,
    payload: RetentionPolicyUpdateRequest,
    session: Session,
    user: RetentionManager,
) -> ApiResponse[RetentionPolicyResponse]:
    result = await RetentionPolicyService(
        session,
        actor_id=user.id,
    ).update(policy_id, payload)
    return ApiResponse(
        success=True,
        message="Retention policy updated successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/retention-policies/run",
    response_model=ApiResponse[RetentionRunResponse],
)
async def run_retention_policy(
    payload: RetentionRunRequest,
    session: Session,
    user: RetentionManager,
    handlers: RetentionHandlers,
) -> ApiResponse[RetentionRunResponse]:
    result = await RetentionService(
        session,
        handlers=handlers,
        actor_id=user.id,
    ).run(
        entity_type=payload.entity_type,
        dry_run=payload.dry_run,
        batch_size=payload.batch_size,
    )
    return ApiResponse(
        success=True,
        message=(
            "Retention dry run completed."
            if payload.dry_run
            else "Retention cleanup completed."
        ),
        data=result,
        errors=None,
    )
