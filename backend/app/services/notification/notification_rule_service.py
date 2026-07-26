"""Scoped notification rule administration and resolution."""

from __future__ import annotations

from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.notification_enums import (
    SYSTEM_CRITICAL_NOTIFICATION_EVENTS,
    NotificationChannel,
    NotificationEventType,
    NotificationSeverity,
)
from app.models.notification_rule import NotificationRule
from app.repositories.audit_log import AuditLogRepository
from app.repositories.notification_rule_repository import (
    NotificationRuleRepository,
)
from app.repositories.notification_template_repository import (
    NotificationTemplateRepository,
)
from app.schemas.notification import (
    NotificationRuleCreateRequest,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
    validate_recipient_configuration,
)
from app.services.notification.errors import notification_error


class NotificationRuleService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID | None,
    ) -> None:
        self.session = session
        self.actor_id = actor_id
        self.repository = NotificationRuleRepository(session)
        self.templates = NotificationTemplateRepository(session)
        self.audit = AuditLogRepository(session)

    async def list(
        self,
        *,
        event_type: NotificationEventType | None,
        channel: NotificationChannel | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationRuleResponse], int, int]:
        rows, total = await self.repository.list_page(
            event_type=event_type,
            channel=channel,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return (
            [NotificationRuleResponse.model_validate(row) for row in rows],
            total,
            ceil(total / page_size) if total else 0,
        )

    async def create(
        self,
        payload: NotificationRuleCreateRequest,
    ) -> NotificationRuleResponse:
        await self._validate_template(
            payload.template_id,
            payload.event_type,
            payload.channel,
        )
        self._validate_mandatory(payload.event_type, payload.is_mandatory)
        values = payload.model_dump()
        values["severity_filter_json"] = [
            item.value for item in payload.severity_filter_json
        ]
        rule = NotificationRule(
            **values,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        await self.repository.add(rule)
        await self.audit.create(
            action=AuditAction.CREATE_NOTIFICATION_RULE,
            user_id=self.actor_id,
            entity_type="NotificationRule",
            entity_id=rule.id,
            description="Notification rule created.",
            new_values=self._audit_values(rule),
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return NotificationRuleResponse.model_validate(rule)

    async def update(
        self,
        rule_id: UUID,
        payload: NotificationRuleUpdateRequest,
    ) -> NotificationRuleResponse:
        rule = await self._get(rule_id, for_update=True)
        old_values = self._audit_values(rule)
        values = payload.model_dump(exclude_unset=True)
        if payload.severity_filter_json is not None:
            values["severity_filter_json"] = [
                item.value for item in payload.severity_filter_json
            ]
        template_id = values.get("template_id")
        if template_id is not None:
            await self._validate_template(
                template_id,
                rule.event_type,
                rule.channel,
            )
        mandatory = values.get("is_mandatory", rule.is_mandatory)
        self._validate_mandatory(rule.event_type, mandatory)
        digest_enabled = values.get("digest_enabled", rule.digest_enabled)
        digest_schedule = values.get("digest_schedule", rule.digest_schedule)
        if digest_enabled and not digest_schedule:
            raise notification_error(
                "Digest schedule is required when digest is enabled.",
                code="NOTIFICATION_TEMPLATE_INVALID",
            )
        recipient_type = values.get("recipient_type", rule.recipient_type)
        recipient_value_json = values.get(
            "recipient_value_json",
            rule.recipient_value_json,
        )
        if "recipient_type" in values or "recipient_value_json" in values:
            values["recipient_value_json"] = validate_recipient_configuration(
                recipient_type,
                recipient_value_json,
            )
        for field, value in values.items():
            setattr(rule, field, value)
        rule.updated_by = self.actor_id
        await self.audit.create(
            action=AuditAction.UPDATE_NOTIFICATION_RULE,
            user_id=self.actor_id,
            entity_type="NotificationRule",
            entity_id=rule.id,
            description="Notification rule updated.",
            old_values=old_values,
            new_values=self._audit_values(rule),
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return NotificationRuleResponse.model_validate(rule)

    async def set_active(
        self,
        rule_id: UUID,
        *,
        active: bool,
    ) -> NotificationRuleResponse:
        rule = await self._get(rule_id, for_update=True)
        old_values = self._audit_values(rule)
        rule.is_active = active
        rule.updated_by = self.actor_id
        await self.audit.create(
            action=AuditAction.UPDATE_NOTIFICATION_RULE,
            user_id=self.actor_id,
            entity_type="NotificationRule",
            entity_id=rule.id,
            description=(
                "Notification rule activated."
                if active
                else "Notification rule deactivated."
            ),
            old_values=old_values,
            new_values=self._audit_values(rule),
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return NotificationRuleResponse.model_validate(rule)

    async def resolve(
        self,
        *,
        event_type: NotificationEventType,
        severity: NotificationSeverity,
        department_id: UUID | None,
        document_type_id: UUID | None,
    ) -> list[NotificationRule]:
        rules = await self.repository.matching_rules(
            event_type=event_type,
            department_id=department_id,
            document_type_id=document_type_id,
        )
        return [
            rule
            for rule in rules
            if not rule.severity_filter_json
            or severity.value in rule.severity_filter_json
        ]

    async def _get(
        self,
        rule_id: UUID,
        *,
        for_update: bool = False,
    ) -> NotificationRule:
        rule = await self.repository.get_by_id(
            rule_id,
            for_update=for_update,
        )
        if rule is None:
            raise notification_error(
                "Notification rule was not found.",
                code="NOTIFICATION_RULE_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return rule

    async def _validate_template(
        self,
        template_id: UUID,
        event_type: NotificationEventType,
        channel: NotificationChannel,
    ) -> None:
        template = await self.templates.get_by_id(template_id)
        if (
            template is None
            or not template.is_active
            or template.event_type != event_type
            or template.channel != channel
        ):
            raise notification_error(
                "Rule template must be active and match the event and channel.",
                code="NOTIFICATION_TEMPLATE_INVALID",
            )

    @staticmethod
    def _validate_mandatory(
        event_type: NotificationEventType,
        mandatory: bool,
    ) -> None:
        if mandatory and event_type not in SYSTEM_CRITICAL_NOTIFICATION_EVENTS:
            raise notification_error(
                "Only documented system-critical rules may be mandatory.",
                code="NOTIFICATION_MANDATORY_RULE_INVALID",
            )

    @staticmethod
    def _audit_values(rule: NotificationRule) -> dict[str, object]:
        recipient_values = rule.recipient_value_json
        recipient_count = sum(
            len(value) for value in recipient_values.values() if isinstance(value, list)
        )
        return {
            "name": rule.name,
            "eventType": rule.event_type.value,
            "channel": rule.channel.value,
            "scopeType": rule.scope_type.value,
            "recipientType": rule.recipient_type.value,
            "recipientCount": recipient_count,
            "templateId": str(rule.template_id),
            "sendImmediately": rule.send_immediately,
            "digestEnabled": rule.digest_enabled,
            "isMandatory": rule.is_mandatory,
            "isActive": rule.is_active,
        }
