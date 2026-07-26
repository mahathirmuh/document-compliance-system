"""Administrative dead-letter API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.sharepoint_enums import DeadLetterStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class DeadLetterJobResponse(ApiSchema):
    id: UUID
    task_name: str
    entity_type: str
    entity_id: UUID | None = None
    attempts: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    error_code: str
    last_error: str
    first_failed_at: datetime
    last_failed_at: datetime
    retry_history: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias="retry_history_json",
    )
    sanitized_arguments: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="sanitized_arguments_json",
    )
    status: DeadLetterStatus
    dismissed_by: UUID | None = None
    dismissed_at: datetime | None = None
    dismissal_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DeadLetterListResponse(PaginationData[DeadLetterJobResponse]):
    pass


DeadLetterJobListResponse = DeadLetterListResponse


class DeadLetterMutationResponse(ApiSchema):
    job_id: UUID
    status: DeadLetterStatus


class DeadLetterActionRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()
