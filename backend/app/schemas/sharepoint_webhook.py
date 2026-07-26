"""Graph webhook and subscription API contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from app.models.sharepoint_enums import GraphSubscriptionStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class GraphSubscriptionCreateRequest(ApiSchema):
    sharepoint_connection_id: UUID
    sync_profile_id: UUID
    resource: str = Field(min_length=1, max_length=2000)
    change_type: str = Field(default="updated", min_length=1, max_length=100)
    notification_url: str = Field(min_length=1, max_length=2000)
    lifecycle_notification_url: str | None = Field(
        default=None,
        max_length=2000,
    )
    client_state: SecretStr
    expiration_datetime: datetime

    @field_validator(
        "notification_url",
        "lifecycle_notification_url",
    )
    @classmethod
    def validate_notification_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError("Graph notification URLs must use absolute HTTPS.")
        return normalized

    @field_validator("client_state")
    @classmethod
    def validate_client_state(cls, value: SecretStr) -> SecretStr:
        if not 32 <= len(value.get_secret_value()) <= 255:
            raise ValueError("Graph webhook client state must be 32-255 characters.")
        return value

    @field_validator("expiration_datetime")
    @classmethod
    def validate_expiration(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Subscription expiration must include a timezone.")
        if value.astimezone(UTC) <= datetime.now(UTC):
            raise ValueError("Subscription expiration must be in the future.")
        return value


class GraphSubscriptionResponse(ApiSchema):
    id: UUID
    sharepoint_connection_id: UUID
    sync_profile_id: UUID
    subscription_id: str
    resource: str
    change_type: str
    notification_url: str
    lifecycle_notification_url: str | None = None
    expiration_datetime: datetime
    status: GraphSubscriptionStatus
    last_renewed_at: datetime | None = None
    last_notification_at: datetime | None = None
    renewal_attempts: int = Field(ge=0)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class GraphSubscriptionListResponse(
    PaginationData[GraphSubscriptionResponse]
):
    pass


class GraphSubscriptionRenewRequest(ApiSchema):
    expiration_datetime: datetime


class GraphSubscriptionDisableRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class GraphWebhookAcceptedResponse(ApiSchema):
    accepted: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    rejected: int = Field(ge=0)
