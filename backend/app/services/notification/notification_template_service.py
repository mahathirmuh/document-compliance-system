"""Safe rendering and administration of notification templates."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from http import HTTPStatus
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.notification_enums import NotificationContentType
from app.models.notification_template import NotificationTemplate
from app.repositories.audit_log import AuditLogRepository
from app.repositories.notification_template_repository import (
    NotificationTemplateRepository,
)
from app.schemas.notification import (
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    NotificationTemplateTestResponse,
    NotificationTemplateUpdateRequest,
)
from app.services.notification.contracts import RenderedNotification
from app.services.notification.errors import notification_error

_VARIABLE_PATTERN = re.compile(
    r"{{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*}}"
)
_UNSAFE_TEMPLATE_MARKERS = ("{%", "{#", "__")


class NotificationTemplateRenderError(ValueError):
    """Template syntax or a required variable is invalid."""


def _resolve_variable(
    variables: Mapping[str, Any],
    path: str,
) -> Any:
    value: Any = variables
    for segment in path.split("."):
        if not isinstance(value, Mapping) or segment not in value:
            raise NotificationTemplateRenderError(
                f"Template variable '{path}' was not supplied."
            )
        value = value[segment]
    if isinstance(value, Mapping) or callable(value):
        raise NotificationTemplateRenderError(
            f"Template variable '{path}' has an unsupported value."
        )
    return value


def render_controlled_template(
    template: str | None,
    variables: Mapping[str, Any],
    *,
    escape_html: bool,
) -> str | None:
    """Replace dotted mapping variables without attribute access or execution."""

    if template is None:
        return None
    if any(marker in template for marker in _UNSAFE_TEMPLATE_MARKERS):
        raise NotificationTemplateRenderError("Template contains unsupported syntax.")

    def replacement(match: re.Match[str]) -> str:
        value = str(_resolve_variable(variables, match.group(1)))
        return html.escape(value, quote=True) if escape_html else value

    rendered = _VARIABLE_PATTERN.sub(replacement, template)
    if "{{" in rendered or "}}" in rendered:
        raise NotificationTemplateRenderError(
            "Template contains invalid variable syntax."
        )
    return rendered


class NotificationTemplateService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID | None,
    ) -> None:
        self.session = session
        self.actor_id = actor_id
        self.repository = NotificationTemplateRepository(session)
        self.audit = AuditLogRepository(session)

    async def list(
        self,
        *,
        event_type: Any = None,
        channel: Any = None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationTemplateResponse], int, int]:
        rows, total = await self.repository.list_page(
            event_type=event_type,
            channel=channel,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return (
            [NotificationTemplateResponse.model_validate(row) for row in rows],
            total,
            ceil(total / page_size) if total else 0,
        )

    async def create(
        self,
        payload: NotificationTemplateCreateRequest,
    ) -> NotificationTemplateResponse:
        template = NotificationTemplate(
            **payload.model_dump(),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        await self.repository.add(template)
        await self.audit.create(
            action=AuditAction.CREATE_NOTIFICATION_TEMPLATE,
            user_id=self.actor_id,
            entity_type="NotificationTemplate",
            entity_id=template.id,
            description="Notification template created.",
            new_values=self._audit_values(template),
        )
        await self.session.commit()
        await self.session.refresh(template)
        return NotificationTemplateResponse.model_validate(template)

    async def update(
        self,
        template_id: UUID,
        payload: NotificationTemplateUpdateRequest,
    ) -> NotificationTemplateResponse:
        template = await self._get(template_id, for_update=True)
        old_values = self._audit_values(template)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        template.updated_by = self.actor_id
        await self.audit.create(
            action=AuditAction.UPDATE_NOTIFICATION_TEMPLATE,
            user_id=self.actor_id,
            entity_type="NotificationTemplate",
            entity_id=template.id,
            description="Notification template updated.",
            old_values=old_values,
            new_values=self._audit_values(template),
        )
        await self.session.commit()
        await self.session.refresh(template)
        return NotificationTemplateResponse.model_validate(template)

    async def test_render(
        self,
        template_id: UUID,
        variables: Mapping[str, Any],
    ) -> NotificationTemplateTestResponse:
        template = await self._get(template_id)
        rendered = self.render(template, variables)
        return NotificationTemplateTestResponse(
            subject=rendered.subject,
            body=rendered.body,
            content_type=rendered.content_type,
            sent=False,
        )

    def render(
        self,
        template: NotificationTemplate,
        variables: Mapping[str, Any],
    ) -> RenderedNotification:
        is_html = template.content_type == NotificationContentType.HTML
        try:
            subject = render_controlled_template(
                template.subject_template,
                variables,
                escape_html=False,
            )
            body = render_controlled_template(
                template.body_template,
                variables,
                escape_html=is_html,
            )
        except NotificationTemplateRenderError as exc:
            raise notification_error(
                str(exc),
                code="NOTIFICATION_TEMPLATE_INVALID",
            ) from exc
        if subject is not None:
            subject = subject.replace("\r", " ").replace("\n", " ")[:500]
        return RenderedNotification(
            subject=subject,
            body=(body or "")[:100_000],
            content_type=template.content_type,
        )

    async def _get(
        self,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> NotificationTemplate:
        template = await self.repository.get_by_id(
            template_id,
            for_update=for_update,
        )
        if template is None:
            raise notification_error(
                "Notification template was not found.",
                code="NOTIFICATION_TEMPLATE_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return template

    @staticmethod
    def _audit_values(template: NotificationTemplate) -> dict[str, Any]:
        return {
            "code": template.code,
            "name": template.name,
            "eventType": template.event_type.value,
            "channel": template.channel.value,
            "contentType": template.content_type.value,
            "languageCode": template.language_code,
            "version": template.version,
            "isDefault": template.is_default,
            "isActive": template.is_active,
        }
