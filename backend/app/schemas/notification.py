"""Public Phase 10 notification API contracts."""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any, Self
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, TypeAdapter, field_validator, model_validator

from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationDeliveryStatus,
    NotificationDigestMode,
    NotificationEventType,
    NotificationRecipientType,
    NotificationScopeType,
    NotificationSeverity,
)
from app.schemas.base import ApiSchema

_SAFE_DIGEST_SCHEDULE = re.compile(r"^[0-9*/,\- ]+$")
_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _validate_internal_action_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or parsed.scheme
        or parsed.netloc
    ):
        raise ValueError("Action URL must be an internal application route.")
    return candidate


def validate_recipient_configuration(
    recipient_type: NotificationRecipientType,
    value: dict[str, Any],
) -> dict[str, Any]:
    key_by_type = {
        NotificationRecipientType.ROLE: "roles",
        NotificationRecipientType.SPECIFIC_USERS: "userIds",
        NotificationRecipientType.SPECIFIC_EMAILS: "emails",
        NotificationRecipientType.TEAMS_CHANNEL: "channelIds",
        NotificationRecipientType.TELEGRAM_CHAT: "chatIds",
    }
    expected_key = key_by_type.get(recipient_type)
    if expected_key is None:
        if value:
            raise ValueError(
                "This recipient type is resolved only from trusted event context."
            )
        return value
    if set(value) != {expected_key}:
        raise ValueError(f"recipientValueJson must contain only '{expected_key}'.")
    items = value[expected_key]
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise ValueError("Recipient list must contain between 1 and 500 items.")
    normalized = [str(item).strip() for item in items]
    if any(not item or len(item) > 320 for item in normalized):
        raise ValueError("Recipient value is invalid.")
    if len({item.casefold() for item in normalized}) != len(normalized):
        raise ValueError("Recipient values must be unique.")
    if recipient_type == NotificationRecipientType.SPECIFIC_USERS:
        for item in normalized:
            UUID(item)
    elif recipient_type == NotificationRecipientType.SPECIFIC_EMAILS:
        for item in normalized:
            _EMAIL_ADAPTER.validate_python(item)
    elif recipient_type == NotificationRecipientType.ROLE:
        allowed_roles = {
            "SUPER_ADMIN",
            "DOCUMENT_CONTROLLER",
            "REVIEWER",
            "DEPARTMENT_USER",
            "AUDITOR",
            "VIEWER",
        }
        if any(item not in allowed_roles for item in normalized):
            raise ValueError("Recipient role is invalid.")
    return {expected_key: normalized}


def validate_digest_schedule(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if (
        len(normalized.split()) != 5
        or len(normalized) > 200
        or not _SAFE_DIGEST_SCHEDULE.fullmatch(normalized)
    ):
        raise ValueError("Digest schedule must be a safe five-field cron.")
    return normalized


class NotificationTemplateCreateRequest(ApiSchema):
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=255)
    event_type: NotificationEventType
    channel: NotificationChannel
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str = Field(min_length=1, max_length=20_000)
    content_type: NotificationContentType = NotificationContentType.PLAIN_TEXT
    language_code: str = Field(default="en", pattern=r"^(id|en|zh)$")
    version: int = Field(default=1, ge=1)
    is_default: bool = False
    is_active: bool = True


class NotificationTemplateUpdateRequest(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str | None = Field(default=None, min_length=1, max_length=20_000)
    content_type: NotificationContentType | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one template field must be supplied.")
        return self


class NotificationTemplateTestRequest(ApiSchema):
    variables: dict[str, Any] = Field(default_factory=dict)
    recipient: str | None = Field(default=None, max_length=320)
    send: bool = False


class NotificationTemplateTestResponse(ApiSchema):
    subject: str | None
    body: str
    content_type: NotificationContentType
    sent: bool = False


class NotificationTemplateResponse(ApiSchema):
    id: UUID
    code: str
    name: str
    event_type: NotificationEventType
    channel: NotificationChannel
    subject_template: str | None
    body_template: str
    content_type: NotificationContentType
    language_code: str
    version: int
    is_default: bool
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class NotificationTemplateListResponse(ApiSchema):
    items: list[NotificationTemplateResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NotificationRuleCreateRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=255)
    event_type: NotificationEventType
    channel: NotificationChannel
    scope_type: NotificationScopeType = NotificationScopeType.GLOBAL
    department_id: UUID | None = None
    document_type_id: UUID | None = None
    severity_filter_json: list[NotificationSeverity] = Field(
        default_factory=list,
        max_length=len(NotificationSeverity),
    )
    recipient_type: NotificationRecipientType
    recipient_value_json: dict[str, Any] = Field(default_factory=dict)
    template_id: UUID
    send_immediately: bool = True
    digest_enabled: bool = False
    digest_schedule: str | None = Field(default=None, max_length=200)
    is_mandatory: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_scope_and_digest(self) -> Self:
        expected = {
            NotificationScopeType.GLOBAL: (False, False),
            NotificationScopeType.DEPARTMENT: (True, False),
            NotificationScopeType.DOCUMENT_TYPE: (False, True),
            NotificationScopeType.DEPARTMENT_DOCUMENT_TYPE: (True, True),
        }[self.scope_type]
        actual = (self.department_id is not None, self.document_type_id is not None)
        if actual != expected:
            raise ValueError("Rule scope identifiers do not match scopeType.")
        if self.digest_enabled and not self.digest_schedule:
            raise ValueError("digestSchedule is required when digest is enabled.")
        self.digest_schedule = validate_digest_schedule(self.digest_schedule)
        self.recipient_value_json = validate_recipient_configuration(
            self.recipient_type,
            self.recipient_value_json,
        )
        if len(set(self.severity_filter_json)) != len(self.severity_filter_json):
            raise ValueError("Severity filters must be unique.")
        return self


class NotificationRuleUpdateRequest(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    severity_filter_json: list[NotificationSeverity] | None = None
    recipient_type: NotificationRecipientType | None = None
    recipient_value_json: dict[str, Any] | None = None
    template_id: UUID | None = None
    send_immediately: bool | None = None
    digest_enabled: bool | None = None
    digest_schedule: str | None = Field(default=None, max_length=200)
    is_mandatory: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one rule field must be supplied.")
        if self.digest_schedule is not None:
            self.digest_schedule = validate_digest_schedule(self.digest_schedule)
        if self.recipient_type is not None and self.recipient_value_json is not None:
            self.recipient_value_json = validate_recipient_configuration(
                self.recipient_type,
                self.recipient_value_json,
            )
        return self


class NotificationRuleResponse(ApiSchema):
    id: UUID
    name: str
    event_type: NotificationEventType
    channel: NotificationChannel
    scope_type: NotificationScopeType
    department_id: UUID | None
    document_type_id: UUID | None
    severity_filter_json: list[str]
    recipient_type: NotificationRecipientType
    recipient_value_json: dict[str, Any]
    template_id: UUID
    send_immediately: bool
    digest_enabled: bool
    digest_schedule: str | None
    is_mandatory: bool
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class NotificationRuleListResponse(ApiSchema):
    items: list[NotificationRuleResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NotificationPreferenceItem(ApiSchema):
    event_type: NotificationEventType
    in_app_enabled: bool = True
    email_enabled: bool = False
    teams_enabled: bool = False
    telegram_enabled: bool = False
    digest_mode: NotificationDigestMode = NotificationDigestMode.NONE
    quiet_hours_enabled: bool = False
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone.") from exc
        return value

    @model_validator(mode="after")
    def validate_quiet_hours(self) -> Self:
        supplied = (
            self.quiet_hours_start is not None and self.quiet_hours_end is not None
        )
        if self.quiet_hours_enabled and not supplied:
            raise ValueError(
                "quietHoursStart and quietHoursEnd are required when quiet hours are enabled."
            )
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("Both quiet-hour boundaries must be supplied together.")
        if supplied and self.quiet_hours_start == self.quiet_hours_end:
            raise ValueError("Quiet-hour boundaries must be different.")
        return self


class NotificationPreferencesUpdateRequest(ApiSchema):
    preferences: list[NotificationPreferenceItem] = Field(
        min_length=1,
        max_length=len(NotificationEventType),
    )

    @model_validator(mode="after")
    def unique_events(self) -> Self:
        events = [item.event_type for item in self.preferences]
        if len(events) != len(set(events)):
            raise ValueError("Each event type may appear only once.")
        return self


class NotificationPreferenceResponse(NotificationPreferenceItem):
    id: UUID | None
    user_id: UUID
    created_at: datetime | None
    updated_at: datetime | None


class InAppNotificationCreate(ApiSchema):
    user_id: UUID
    event_type: NotificationEventType
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1, max_length=20_000)
    severity: NotificationSeverity = NotificationSeverity.INFORMATION
    related_entity_type: str | None = Field(default=None, max_length=100)
    related_entity_id: UUID | None = None
    action_url: str | None = Field(default=None, max_length=2000)
    expires_at: datetime | None = None

    @field_validator("action_url")
    @classmethod
    def internal_action_url(cls, value: str | None) -> str | None:
        return _validate_internal_action_url(value)


class InAppNotificationResponse(ApiSchema):
    id: UUID
    user_id: UUID
    event_type: NotificationEventType
    title: str
    message: str
    severity: NotificationSeverity
    related_entity_type: str | None
    related_entity_id: UUID | None
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    expires_at: datetime | None


class NotificationListResponse(ApiSchema):
    items: list[InAppNotificationResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class UnreadNotificationCountResponse(ApiSchema):
    unread_count: int = Field(ge=0)


class NotificationMutationResponse(ApiSchema):
    notification_id: UUID | None = None
    affected_count: int = Field(default=1, ge=0)


class NotificationDeliveryResponse(ApiSchema):
    id: UUID
    event_type: NotificationEventType
    channel: NotificationChannel
    template_id: UUID | None
    recipient_type: NotificationRecipientType
    recipient_reference: str
    subject: str | None
    payload_hash: str
    status: NotificationDeliveryStatus
    attempt_count: int
    maximum_attempts: int
    provider_message_id: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None
    next_retry_at: datetime | None
    error_code: str | None
    error_message: str | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryListResponse(ApiSchema):
    items: list[NotificationDeliveryResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NotificationRetryResponse(ApiSchema):
    delivery_id: UUID
    status: NotificationDeliveryStatus
