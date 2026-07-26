"""Authenticated Microsoft Graph subscription administration."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.models.sharepoint_enums import GraphSubscriptionStatus
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.sharepoint_webhook import (
    GraphSubscriptionCreateRequest,
    GraphSubscriptionDisableRequest,
    GraphSubscriptionListResponse,
    GraphSubscriptionRenewRequest,
    GraphSubscriptionResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint.subscription_service import (
    GraphSubscriptionService,
)

router = APIRouter(
    prefix="/integrations/sharepoint/subscriptions",
    tags=["Microsoft Graph Subscriptions"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
SubscriptionViewer = Annotated[
    User, Depends(require_permissions("sharepoint:view"))
]
SubscriptionManager = Annotated[
    User, Depends(require_permissions("sharepoint:configure"))
]


@router.get(
    "",
    response_model=ApiResponse[GraphSubscriptionListResponse],
)
async def list_graph_subscriptions(
    session: Session,
    settings: Configuration,
    user: SubscriptionViewer,
    metadata: Metadata,
    statuses: Annotated[
        list[GraphSubscriptionStatus] | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[GraphSubscriptionListResponse]:
    result = await GraphSubscriptionService(
        session, settings, user, metadata
    ).list(
        statuses=statuses,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Microsoft Graph subscriptions retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "",
    response_model=ApiResponse[GraphSubscriptionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_graph_subscription(
    payload: GraphSubscriptionCreateRequest,
    session: Session,
    settings: Configuration,
    user: SubscriptionManager,
    metadata: Metadata,
) -> ApiResponse[GraphSubscriptionResponse]:
    result = await GraphSubscriptionService(
        session, settings, user, metadata
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Microsoft Graph subscription created successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/{subscription_id}/renew",
    response_model=ApiResponse[GraphSubscriptionResponse],
)
async def renew_graph_subscription(
    subscription_id: UUID,
    payload: GraphSubscriptionRenewRequest,
    session: Session,
    settings: Configuration,
    user: SubscriptionManager,
    metadata: Metadata,
) -> ApiResponse[GraphSubscriptionResponse]:
    result = await GraphSubscriptionService(
        session, settings, user, metadata
    ).renew(
        subscription_id,
        expiration_datetime=payload.expiration_datetime,
    )
    return ApiResponse(
        success=True,
        message="Microsoft Graph subscription renewed successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/{subscription_id}/disable",
    response_model=ApiResponse[GraphSubscriptionResponse],
)
async def disable_graph_subscription(
    subscription_id: UUID,
    payload: GraphSubscriptionDisableRequest,
    session: Session,
    settings: Configuration,
    user: SubscriptionManager,
    metadata: Metadata,
) -> ApiResponse[GraphSubscriptionResponse]:
    result = await GraphSubscriptionService(
        session, settings, user, metadata
    ).disable(subscription_id, reason=payload.reason)
    return ApiResponse(
        success=True,
        message="Microsoft Graph subscription disabled.",
        data=result,
        errors=None,
    )


@router.post(
    "/{subscription_id}/delete",
    response_model=ApiResponse[dict[str, bool]],
)
async def delete_graph_subscription(
    subscription_id: UUID,
    session: Session,
    settings: Configuration,
    user: SubscriptionManager,
    metadata: Metadata,
) -> ApiResponse[dict[str, bool]]:
    await GraphSubscriptionService(
        session, settings, user, metadata
    ).delete_remote(subscription_id)
    return ApiResponse(
        success=True,
        message="Microsoft Graph subscription deleted.",
        data={"deleted": True},
        errors=None,
    )
