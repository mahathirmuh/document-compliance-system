"""User-owned in-app notification query and mutation service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from math import ceil
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.in_app_notification_repository import (
    InAppNotificationRepository,
)
from app.repositories.notification_template_repository import (
    NotificationTemplateRepository,
)
from app.schemas.notification import (
    InAppNotificationResponse,
    NotificationListResponse,
    NotificationMutationResponse,
    UnreadNotificationCountResponse,
)
from app.schemas.notification_internal import NotificationTaskPayload
from app.services.notification.contracts import NotificationEvent
from app.services.notification.errors import notification_error
from app.services.notification.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification.notification_recipient_service import (
    NotificationRecipientService,
)
from app.services.notification.notification_rule_service import (
    NotificationRuleService,
)
from app.services.notification.notification_template_service import (
    NotificationTemplateService,
)
from app.utils.datetime import utc_now


class NotificationService:
    def __init__(self, session: AsyncSession, *, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repository = InAppNotificationRepository(session)

    async def list(
        self,
        *,
        unread_only: bool,
        page: int,
        page_size: int,
    ) -> NotificationListResponse:
        rows, total = await self.repository.list_page(
            user_id=self.user_id,
            unread_only=unread_only,
            now=utc_now(),
            page=page,
            page_size=page_size,
        )
        return NotificationListResponse(
            items=[InAppNotificationResponse.model_validate(row) for row in rows],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def unread_count(self) -> UnreadNotificationCountResponse:
        count = await self.repository.unread_count(
            user_id=self.user_id,
            now=utc_now(),
        )
        return UnreadNotificationCountResponse(unread_count=count)

    async def mark_read(
        self,
        notification_id: UUID,
    ) -> NotificationMutationResponse:
        notification = await self._get(notification_id, for_update=True)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = utc_now()
        await self.session.commit()
        return NotificationMutationResponse(notification_id=notification.id)

    async def mark_all_read(self) -> NotificationMutationResponse:
        now = utc_now()
        affected = await self.repository.mark_all_read(
            user_id=self.user_id,
            read_at=now,
            now=now,
        )
        await self.session.commit()
        return NotificationMutationResponse(affected_count=affected)

    async def dismiss(
        self,
        notification_id: UUID,
    ) -> NotificationMutationResponse:
        notification = await self._get(notification_id, for_update=True)
        notification.dismissed_at = utc_now()
        await self.session.commit()
        return NotificationMutationResponse(notification_id=notification.id)

    async def _get(self, notification_id: UUID, *, for_update: bool):
        notification = await self.repository.get_for_user(
            notification_id=notification_id,
            user_id=self.user_id,
            for_update=for_update,
        )
        if notification is None:
            raise notification_error(
                "Notification was not found.",
                code="NOTIFICATION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return notification


class NotificationQueuePublisher(Protocol):
    async def publish(
        self,
        payload: Mapping[str, Any],
        *,
        digest: bool,
    ) -> str | None: ...


@dataclass(frozen=True, slots=True)
class NotificationEventDispatchSummary:
    matched_rule_count: int
    queued_delivery_count: int
    skipped_delivery_count: int
    failed_publish_count: int


class NotificationOrchestrationService:
    """Resolve rules, recipients, preferences, templates, and queue payloads."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        publisher: NotificationQueuePublisher,
    ) -> None:
        self.session = session
        self.publisher = publisher
        self.rules = NotificationRuleService(session, actor_id=None)
        self.templates = NotificationTemplateRepository(session)
        self.template_service = NotificationTemplateService(
            session,
            actor_id=None,
        )
        self.recipients = NotificationRecipientService(session)

    async def emit(
        self,
        event: NotificationEvent,
    ) -> NotificationEventDispatchSummary:
        rules = await self.rules.resolve(
            event_type=event.event_type,
            severity=event.severity,
            department_id=event.department_id,
            document_type_id=event.document_type_id,
        )
        queued = skipped = failed = 0
        for rule in rules:
            template = await self.templates.get_by_id(rule.template_id)
            if template is None or not template.is_active:
                skipped += 1
                continue
            rendered = self.template_service.render(
                template,
                event.variables,
            )
            for recipient in await self.recipients.resolve(rule, event):
                if recipient.user_id is not None:
                    allowed = await NotificationPreferenceService(
                        self.session,
                        user_id=recipient.user_id,
                    ).delivery_allowed(
                        event_type=event.event_type,
                        channel=rule.channel,
                        mandatory_rule=rule.is_mandatory,
                        now=event.occurred_at or utc_now(),
                    )
                    if not allowed:
                        skipped += 1
                        continue
                try:
                    payload = NotificationTaskPayload(
                        event_type=event.event_type,
                        channel=rule.channel,
                        recipient_type=recipient.recipient_type,
                        recipient_reference=recipient.reference,
                        recipient_user_id=recipient.user_id,
                        subject=rendered.subject,
                        body=rendered.body,
                        content_type=rendered.content_type,
                        severity=event.severity,
                        related_entity_type=event.related_entity_type,
                        related_entity_id=event.related_entity_id,
                        action_url=event.action_url,
                        template_id=template.id,
                    )
                    await self.publisher.publish(
                        payload.model_dump(mode="json", by_alias=True),
                        digest=rule.digest_enabled and not rule.send_immediately,
                    )
                    queued += 1
                except Exception:  # noqa: BLE001 - queue drivers vary
                    # Notification enqueue failure must not roll back the
                    # already committed application event transaction.
                    failed += 1
        return NotificationEventDispatchSummary(
            matched_rule_count=len(rules),
            queued_delivery_count=queued,
            skipped_delivery_count=skipped,
            failed_publish_count=failed,
        )
