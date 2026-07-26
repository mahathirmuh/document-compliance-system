"""SharePoint sync, remote-version, and conflict API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.sharepoint_enums import (
    ConflictPolicy,
    DeletePolicy,
    FolderMappingScope,
    SharePointSyncJobStatus,
    SyncConflictResolution,
    SyncConflictStatus,
    SyncConflictType,
    SyncDirection,
    SyncItemOperation,
    SyncItemStatus,
    SyncJobType,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class SharePointSyncProfileWrite(ApiSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    sharepoint_connection_id: UUID
    direction: SyncDirection = SyncDirection.OUTBOUND
    scope_type: FolderMappingScope = FolderMappingScope.GLOBAL
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    folder_mapping_id: UUID | None = None
    metadata_mapping_profile: dict[str, Any] = Field(default_factory=dict)
    conflict_policy: ConflictPolicy = ConflictPolicy.MANUAL
    delete_policy: DeletePolicy = DeletePolicy.IGNORE_REMOTE_DELETE
    sync_schedule: str | None = Field(default=None, max_length=255)
    delta_sync_enabled: bool = True
    webhook_enabled: bool = False
    is_active: bool = False

    @field_validator("sync_schedule")
    @classmethod
    def validate_sync_schedule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or normalized.casefold() == "manual":
            return None
        fields = normalized.split()
        if len(fields) != 5:
            raise ValueError(
                "syncSchedule must be a five-field cron expression."
            )
        from celery.schedules import crontab

        crontab(
            minute=fields[0],
            hour=fields[1],
            day_of_month=fields[2],
            month_of_year=fields[3],
            day_of_week=fields[4],
        )
        return " ".join(fields)

    @model_validator(mode="after")
    def validate_policy(self) -> SharePointSyncProfileWrite:
        requirements = {
            FolderMappingScope.GLOBAL: (False, False, False),
            FolderMappingScope.DEPARTMENT: (True, False, False),
            FolderMappingScope.SECTION: (False, True, False),
            FolderMappingScope.DOCUMENT_TYPE: (False, False, True),
            FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE: (
                True,
                False,
                True,
            ),
            FolderMappingScope.SECTION_DOCUMENT_TYPE: (
                False,
                True,
                True,
            ),
        }
        supplied = (
            self.department_id is not None,
            self.section_id is not None,
            self.document_type_id is not None,
        )
        if supplied != requirements[self.scope_type]:
            raise ValueError(
                "Sync profile identifiers must match scopeType."
            )
        if (
            self.direction is SyncDirection.BIDIRECTIONAL
            and self.conflict_policy is None
        ):
            raise ValueError(
                "Bidirectional sync requires a conflict policy."
            )
        return self


class SharePointSyncProfileCreateRequest(SharePointSyncProfileWrite):
    pass


class SharePointSyncProfileUpdateRequest(SharePointSyncProfileWrite):
    pass


class SharePointSyncProfileResponse(SharePointSyncProfileWrite):
    id: UUID
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SharePointSyncProfileListResponse(
    PaginationData[SharePointSyncProfileResponse]
):
    pass


class SharePointSyncRunRequest(ApiSchema):
    job_type: SyncJobType = SyncJobType.MANUAL_INCREMENTAL
    scope: dict[str, Any] = Field(default_factory=dict)


class SharePointDeltaResetRequest(ApiSchema):
    confirmation_reason: str = Field(min_length=5, max_length=2000)

    @field_validator("confirmation_reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class SharePointSyncJobCreateRequest(ApiSchema):
    sync_profile_id: UUID
    job_type: SyncJobType = SyncJobType.MANUAL_INCREMENTAL
    direction: SyncDirection | None = None
    scope: dict[str, Any] = Field(default_factory=dict)


class SharePointSyncJobResponse(ApiSchema):
    id: UUID
    sync_profile_id: UUID
    sharepoint_connection_id: UUID
    job_type: SyncJobType
    direction: SyncDirection
    status: SharePointSyncJobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None = None
    scope: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="scope_json",
    )
    requested_by: UUID | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    attempt_number: int = Field(ge=1)
    maximum_attempts: int = Field(ge=1)
    items_discovered: int = Field(ge=0)
    items_processed: int = Field(ge=0)
    items_created: int = Field(ge=0)
    items_updated: int = Field(ge=0)
    items_skipped: int = Field(ge=0)
    items_conflicted: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    error_code: str | None = None
    error_message: str | None = None
    result_summary: dict[str, Any] | None = Field(
        default=None,
        validation_alias="result_summary_json",
    )
    created_at: datetime
    updated_at: datetime

    @field_validator("result_summary", mode="before")
    @classmethod
    def hide_internal_delta_state(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        sanitized = {
            key: item
            for key, item in value.items()
            if key
            not in {
                "deltaTokenCandidateHash",
                "deltaTokenBefore",
                "deltaTokenAfter",
                "deltaLink",
            }
        }
        if "deltaTokenPersisted" in sanitized:
            sanitized["deltaStateAdvanced"] = sanitized.pop(
                "deltaTokenPersisted"
            )
        return sanitized


class SharePointSyncJobListResponse(
    PaginationData[SharePointSyncJobResponse]
):
    pass


class SharePointSyncItemResponse(ApiSchema):
    id: UUID
    sync_job_id: UUID
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None
    remote_drive_id: str | None = None
    remote_item_id: str | None = None
    remote_path: str | None = None
    remote_web_url: str | None = None
    operation: SyncItemOperation
    status: SyncItemStatus
    local_hash_before: str | None = None
    local_hash_after: str | None = None
    remote_etag_before: str | None = None
    remote_etag_after: str | None = None
    remote_size: int | None = Field(default=None, ge=0)
    conflict_id: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata_json",
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class SharePointSyncItemListResponse(
    PaginationData[SharePointSyncItemResponse]
):
    pass


class SharePointConflictResponse(ApiSchema):
    id: UUID
    sync_job_id: UUID
    sync_item_id: UUID | None = None
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None
    remote_item_id: str | None = None
    conflict_type: SyncConflictType
    status: SyncConflictStatus
    local_version: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="local_version_json",
    )
    remote_version: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="remote_version_json",
    )
    detected_at: datetime
    assigned_to: UUID | None = None
    resolution: SyncConflictResolution | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution_comment: str | None = None
    result_document_file_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SharePointConflictListResponse(
    PaginationData[SharePointConflictResponse]
):
    pass


class SharePointConflictAssignRequest(ApiSchema):
    assigned_to: UUID


class SharePointConflictResolveRequest(ApiSchema):
    resolution: SyncConflictResolution
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str) -> str:
        return value.strip()


class SharePointConflictIgnoreRequest(ApiSchema):
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str) -> str:
        return value.strip()


class SharePointFileStatusResponse(ApiSchema):
    document_file_id: UUID
    storage_provider: str
    remote_sync_status: str | None = None
    sharepoint_connection_id: UUID | None = None
    remote_drive_id: str | None = None
    remote_item_id: str | None = None
    remote_path: str | None = None
    remote_etag: str | None = None
    remote_version_id: str | None = None
    remote_last_modified_at: datetime | None = None
    remote_size: int | None = Field(default=None, ge=0)
    last_synced_at: datetime | None = None
    sync_error_code: str | None = None
    sync_error_message: str | None = None


class SharePointFileVersionResponse(ApiSchema):
    id: UUID
    document_file_id: UUID
    remote_drive_id: str
    remote_item_id: str
    remote_version_id: str
    remote_etag: str | None = None
    remote_last_modified_at: datetime | None = None
    remote_last_modified_by: str | None = None
    remote_size: int | None = Field(default=None, ge=0)
    local_sha256_hash: str | None = None
    sync_job_id: UUID | None = None
    created_at: datetime


class SharePointFileVersionListResponse(
    PaginationData[SharePointFileVersionResponse]
):
    pass
