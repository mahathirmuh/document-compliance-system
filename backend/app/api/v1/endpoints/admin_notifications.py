"""Administrator notification template, rule, and delivery endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.database.session import get_db_session
from app.models.notification_enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.notification import (
    NotificationDeliveryListResponse,
    NotificationRetryResponse,
    NotificationRuleCreateRequest,
    NotificationRuleListResponse,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
    NotificationTemplateCreateRequest,
    NotificationTemplateListResponse,
    NotificationTemplateResponse,
    NotificationTemplateTestRequest,
    NotificationTemplateTestResponse,
    NotificationTemplateUpdateRequest,
)
from app.services.notification.notification_delivery_service import (
    NotificationDeliveryService,
)
from app.services.notification.notification_retry_service import (
    NotificationRetryPublisher,
    NotificationRetryService,
)
from app.services.notification.notification_rule_service import (
    NotificationRuleService,
)
from app.services.notification.notification_template_service import (
    NotificationTemplateService,
)

router = APIRouter(prefix="/admin", tags=["Notification Administration"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
TemplateManager = Annotated[
    User,
    Depends(require_permissions("notifications:manage_templates")),
]
RuleManager = Annotated[
    User,
    Depends(require_permissions("notifications:manage_rules")),
]
DeliveryViewer = Annotated[
    User,
    Depends(require_permissions("notifications:view_deliveries")),
]
DeliveryRetrier = Annotated[
    User,
    Depends(require_permissions("notifications:retry_delivery")),
]


def get_notification_retry_publisher() -> NotificationRetryPublisher | None:
    """Override with a publisher that rehydrates and queues the delivery."""

    return None


RetryPublisher = Annotated[
    NotificationRetryPublisher | None,
    Depends(get_notification_retry_publisher),
]


@router.get(
    "/notification-templates",
    response_model=ApiResponse[NotificationTemplateListResponse],
)
async def list_notification_templates(
    session: Session,
    user: TemplateManager,
    event_type: Annotated[
        NotificationEventType | None,
        Query(alias="eventType"),
    ] = None,
    channel: NotificationChannel | None = None,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[NotificationTemplateListResponse]:
    items, total, total_pages = await NotificationTemplateService(
        session,
        actor_id=user.id,
    ).list(
        event_type=event_type,
        channel=channel,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    result = NotificationTemplateListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
    )
    return ApiResponse(
        success=True,
        message="Notification templates retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/notification-templates",
    response_model=ApiResponse[NotificationTemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_template(
    payload: NotificationTemplateCreateRequest,
    session: Session,
    user: TemplateManager,
) -> ApiResponse[NotificationTemplateResponse]:
    result = await NotificationTemplateService(
        session,
        actor_id=user.id,
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Notification template created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/notification-templates/{template_id}",
    response_model=ApiResponse[NotificationTemplateResponse],
)
async def update_notification_template(
    template_id: UUID,
    payload: NotificationTemplateUpdateRequest,
    session: Session,
    user: TemplateManager,
) -> ApiResponse[NotificationTemplateResponse]:
    result = await NotificationTemplateService(
        session,
        actor_id=user.id,
    ).update(template_id, payload)
    return ApiResponse(
        success=True,
        message="Notification template updated successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/notification-templates/{template_id}/test",
    response_model=ApiResponse[NotificationTemplateTestResponse],
)
async def test_notification_template(
    template_id: UUID,
    payload: NotificationTemplateTestRequest,
    session: Session,
    user: TemplateManager,
) -> ApiResponse[NotificationTemplateTestResponse]:
    result = await NotificationTemplateService(
        session,
        actor_id=user.id,
    ).test_render(template_id, payload.variables)
    return ApiResponse(
        success=True,
        message="Notification template rendered safely.",
        data=result,
        errors=None,
    )


@router.get(
    "/notification-rules",
    response_model=ApiResponse[NotificationRuleListResponse],
)
async def list_notification_rules(
    session: Session,
    user: RuleManager,
    event_type: Annotated[
        NotificationEventType | None,
        Query(alias="eventType"),
    ] = None,
    channel: NotificationChannel | None = None,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[NotificationRuleListResponse]:
    items, total, total_pages = await NotificationRuleService(
        session,
        actor_id=user.id,
    ).list(
        event_type=event_type,
        channel=channel,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    result = NotificationRuleListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
    )
    return ApiResponse(
        success=True,
        message="Notification rules retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/notification-rules",
    response_model=ApiResponse[NotificationRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_rule(
    payload: NotificationRuleCreateRequest,
    session: Session,
    user: RuleManager,
) -> ApiResponse[NotificationRuleResponse]:
    result = await NotificationRuleService(
        session,
        actor_id=user.id,
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Notification rule created successfully.",
        data=result,
        errors=None,
    )


@router.put(
    "/notification-rules/{rule_id}",
    response_model=ApiResponse[NotificationRuleResponse],
)
async def update_notification_rule(
    rule_id: UUID,
    payload: NotificationRuleUpdateRequest,
    session: Session,
    user: RuleManager,
) -> ApiResponse[NotificationRuleResponse]:
    result = await NotificationRuleService(
        session,
        actor_id=user.id,
    ).update(rule_id, payload)
    return ApiResponse(
        success=True,
        message="Notification rule updated successfully.",
        data=result,
        errors=None,
    )


async def _set_rule_active(
    rule_id: UUID,
    *,
    active: bool,
    session: AsyncSession,
    user: User,
) -> ApiResponse[NotificationRuleResponse]:
    result = await NotificationRuleService(
        session,
        actor_id=user.id,
    ).set_active(rule_id, active=active)
    return ApiResponse(
        success=True,
        message=(
            "Notification rule activated."
            if active
            else "Notification rule deactivated."
        ),
        data=result,
        errors=None,
    )


@router.post(
    "/notification-rules/{rule_id}/activate",
    response_model=ApiResponse[NotificationRuleResponse],
)
async def activate_notification_rule(
    rule_id: UUID,
    session: Session,
    user: RuleManager,
) -> ApiResponse[NotificationRuleResponse]:
    return await _set_rule_active(
        rule_id,
        active=True,
        session=session,
        user=user,
    )


@router.post(
    "/notification-rules/{rule_id}/deactivate",
    response_model=ApiResponse[NotificationRuleResponse],
)
async def deactivate_notification_rule(
    rule_id: UUID,
    session: Session,
    user: RuleManager,
) -> ApiResponse[NotificationRuleResponse]:
    return await _set_rule_active(
        rule_id,
        active=False,
        session=session,
        user=user,
    )


@router.get(
    "/notification-deliveries",
    response_model=ApiResponse[NotificationDeliveryListResponse],
)
async def list_notification_deliveries(
    session: Session,
    user: DeliveryViewer,
    delivery_status: Annotated[
        NotificationDeliveryStatus | None,
        Query(alias="status"),
    ] = None,
    event_type: Annotated[
        NotificationEventType | None,
        Query(alias="eventType"),
    ] = None,
    channel: NotificationChannel | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApiResponse[NotificationDeliveryListResponse]:
    result = await NotificationDeliveryService(session).list(
        status=delivery_status,
        event_type=event_type,
        channel=channel,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="Notification deliveries retrieved successfully.",
        data=result,
        errors=None,
    )


@router.post(
    "/notification-deliveries/{delivery_id}/retry",
    response_model=ApiResponse[NotificationRetryResponse],
)
async def retry_notification_delivery(
    delivery_id: UUID,
    session: Session,
    user: DeliveryRetrier,
    publisher: RetryPublisher,
) -> ApiResponse[NotificationRetryResponse]:
    result = await NotificationRetryService(
        session,
        publisher=publisher,
        actor_id=user.id,
    ).queue_manual_retry(delivery_id)
    return ApiResponse(
        success=True,
        message="Notification delivery retry queued.",
        data=result,
        errors=None,
    )
