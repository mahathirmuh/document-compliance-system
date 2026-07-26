"""User-owned in-app notifications and preference endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMutationResponse,
    NotificationPreferenceResponse,
    NotificationPreferencesUpdateRequest,
    UnreadNotificationCountResponse,
)
from app.services.notification.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification.notification_service import NotificationService

router = APIRouter(tags=["Notifications"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
NotificationViewer = Annotated[
    User,
    Depends(require_permissions("notifications:view")),
]
PreferenceEditor = Annotated[
    User,
    Depends(require_permissions("notifications:update_preferences")),
]


@router.get(
    "/notifications",
    response_model=ApiResponse[NotificationListResponse],
)
async def list_notifications(
    session: Session,
    user: NotificationViewer,
    unread_only: Annotated[bool, Query(alias="unreadOnly")] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[NotificationListResponse]:
    result = await NotificationService(session, user_id=user.id).list(
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Notifications retrieved successfully.",
        data=result,
        errors=None,
    )


@router.get(
    "/notifications/unread-count",
    response_model=ApiResponse[UnreadNotificationCountResponse],
)
async def unread_notification_count(
    session: Session,
    user: NotificationViewer,
) -> ApiResponse[UnreadNotificationCountResponse]:
    result = await NotificationService(
        session,
        user_id=user.id,
    ).unread_count()
    return ApiResponse(
        success=True,
        message="Unread notification count retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/notifications/read-all",
    response_model=ApiResponse[NotificationMutationResponse],
)
async def read_all_notifications(
    session: Session,
    user: NotificationViewer,
) -> ApiResponse[NotificationMutationResponse]:
    result = await NotificationService(
        session,
        user_id=user.id,
    ).mark_all_read()
    return ApiResponse(
        success=True,
        message="All notifications marked as read.",
        data=result,
        errors=None,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=ApiResponse[NotificationMutationResponse],
)
async def read_notification(
    notification_id: UUID,
    session: Session,
    user: NotificationViewer,
) -> ApiResponse[NotificationMutationResponse]:
    result = await NotificationService(
        session,
        user_id=user.id,
    ).mark_read(notification_id)
    return ApiResponse(
        success=True,
        message="Notification marked as read.",
        data=result,
        errors=None,
    )


@router.post(
    "/notifications/{notification_id}/dismiss",
    response_model=ApiResponse[NotificationMutationResponse],
)
async def dismiss_notification(
    notification_id: UUID,
    session: Session,
    user: NotificationViewer,
) -> ApiResponse[NotificationMutationResponse]:
    result = await NotificationService(
        session,
        user_id=user.id,
    ).dismiss(notification_id)
    return ApiResponse(
        success=True,
        message="Notification dismissed.",
        data=result,
        errors=None,
    )


@router.get(
    "/notification-preferences",
    response_model=ApiResponse[list[NotificationPreferenceResponse]],
)
async def list_notification_preferences(
    session: Session,
    user: NotificationViewer,
) -> ApiResponse[list[NotificationPreferenceResponse]]:
    result = await NotificationPreferenceService(
        session,
        user_id=user.id,
    ).list()
    return ApiResponse(
        success=True,
        message="Notification preferences retrieved successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/notification-preferences",
    response_model=ApiResponse[list[NotificationPreferenceResponse]],
)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    session: Session,
    user: PreferenceEditor,
) -> ApiResponse[list[NotificationPreferenceResponse]]:
    result = await NotificationPreferenceService(
        session,
        user_id=user.id,
    ).update(payload)
    return ApiResponse(
        success=True,
        message="Notification preferences updated successfully.",
        data=result,
        errors=None,
    )
