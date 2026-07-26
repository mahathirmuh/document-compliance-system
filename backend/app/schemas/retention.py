"""Retention administration and dry-run result contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from app.models.data_retention_policy import (
    RetentionEntityType,
    RetentionScopeType,
)
from app.schemas.base import ApiSchema


class RetentionPolicyCreateRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=255)
    entity_type: RetentionEntityType
    scope_type: RetentionScopeType = RetentionScopeType.GLOBAL
    department_id: UUID | None = None
    document_type_id: UUID | None = None
    retention_days: int = Field(ge=1, le=36_500)
    archive_after_days: int | None = Field(default=None, ge=1, le=36_500)
    delete_after_days: int | None = Field(default=None, ge=1, le=36_500)
    legal_hold_enabled: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        expected = {
            RetentionScopeType.GLOBAL: (False, False),
            RetentionScopeType.DEPARTMENT: (True, False),
            RetentionScopeType.DOCUMENT_TYPE: (False, True),
            RetentionScopeType.DEPARTMENT_DOCUMENT_TYPE: (True, True),
        }[self.scope_type]
        if (
            self.department_id is not None,
            self.document_type_id is not None,
        ) != expected:
            raise ValueError("Policy scope identifiers do not match scopeType.")
        if (
            self.archive_after_days is not None
            and self.delete_after_days is not None
            and self.delete_after_days < self.archive_after_days
        ):
            raise ValueError("deleteAfterDays cannot precede archiveAfterDays.")
        return self


class RetentionPolicyUpdateRequest(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    retention_days: int | None = Field(default=None, ge=1, le=36_500)
    archive_after_days: int | None = Field(default=None, ge=1, le=36_500)
    delete_after_days: int | None = Field(default=None, ge=1, le=36_500)
    legal_hold_enabled: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one retention field must be supplied.")
        return self


class RetentionPolicyResponse(ApiSchema):
    id: UUID
    name: str
    entity_type: RetentionEntityType
    scope_type: RetentionScopeType
    department_id: UUID | None
    document_type_id: UUID | None
    retention_days: int
    archive_after_days: int | None
    delete_after_days: int | None
    legal_hold_enabled: bool
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class RetentionPolicyListResponse(ApiSchema):
    items: list[RetentionPolicyResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class RetentionRunRequest(ApiSchema):
    entity_type: RetentionEntityType
    dry_run: bool = True
    batch_size: int = Field(default=500, ge=1, le=5000)


class RetentionRunResponse(ApiSchema):
    entity_type: RetentionEntityType
    dry_run: bool
    scanned_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    archived_count: int = Field(ge=0)
    soft_deleted_count: int = Field(ge=0)
    permanently_deleted_count: int = Field(ge=0)
    legal_hold_skipped_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
