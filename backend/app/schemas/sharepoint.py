"""Public non-secret SharePoint connection and mapping contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.sharepoint_enums import (
    FolderMappingScope,
    MetadataDataType,
    MetadataDirection,
    SharePointAuthMode,
    SharePointConnectionStatus,
)
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


def _safe_remote_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/").strip("/")
    if not normalized or any(
        part in {"", ".", ".."} for part in normalized.split("/")
    ):
        raise ValueError("A safe relative SharePoint path is required.")
    return normalized


class SharePointConnectionCreateRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    tenant_id_reference: str = Field(min_length=1, max_length=255)
    site_hostname: str = Field(min_length=1, max_length=255)
    site_path: str = Field(min_length=1, max_length=1000)
    site_id: str | None = Field(default=None, max_length=1000)
    drive_id: str | None = Field(default=None, max_length=1000)
    library_name: str = Field(min_length=1, max_length=255)
    root_folder_path: str = Field(
        default="DocumentCompliance",
        min_length=1,
        max_length=1000,
    )
    auth_mode: SharePointAuthMode = SharePointAuthMode.CLIENT_SECRET
    is_default: bool = False

    @field_validator("root_folder_path")
    @classmethod
    def validate_root_path(cls, value: str) -> str:
        return _safe_remote_path(value)

    @field_validator("site_hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "/" in normalized
            or "\\" in normalized
            or not normalized.endswith(".sharepoint.com")
        ):
            raise ValueError("A SharePoint Online hostname is required.")
        return normalized


class SharePointConnectionUpdateRequest(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    tenant_id_reference: str | None = Field(
        default=None, min_length=1, max_length=255
    )
    site_hostname: str | None = Field(
        default=None, min_length=1, max_length=255
    )
    site_path: str | None = Field(
        default=None, min_length=1, max_length=1000
    )
    site_id: str | None = Field(default=None, max_length=1000)
    drive_id: str | None = Field(default=None, max_length=1000)
    library_name: str | None = Field(
        default=None, min_length=1, max_length=255
    )
    root_folder_path: str | None = Field(
        default=None, min_length=1, max_length=1000
    )
    auth_mode: SharePointAuthMode | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("root_folder_path")
    @classmethod
    def validate_root_path(cls, value: str | None) -> str | None:
        return _safe_remote_path(value) if value is not None else None

    @field_validator("site_hostname")
    @classmethod
    def validate_hostname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return SharePointConnectionCreateRequest.validate_hostname(value)


class SharePointConnectionResponse(ApiSchema):
    id: UUID
    name: str
    description: str | None = None
    tenant_id_reference: str
    site_hostname: str
    site_path: str
    site_id: str | None = None
    drive_id: str | None = None
    library_name: str
    root_folder_path: str
    auth_mode: SharePointAuthMode
    status: SharePointConnectionStatus
    is_default: bool
    is_active: bool
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SharePointConnectionListResponse(
    PaginationData[SharePointConnectionResponse]
):
    pass


class SharePointConnectionTestResponse(ApiSchema):
    connection_id: UUID
    status: SharePointConnectionStatus
    site_id: str | None = None
    drive_id: str | None = None
    site_read: bool = False
    drive_read: bool = False
    tested_at: datetime
    message: str


class SharePointSiteResponse(ApiSchema):
    id: str
    display_name: str | None = None
    name: str | None = None
    web_url: str | None = None


class SharePointDriveResponse(ApiSchema):
    id: str
    name: str
    drive_type: str | None = None
    web_url: str | None = None


class SharePointFolderResponse(ApiSchema):
    id: str
    name: str
    web_url: str | None = None
    parent_reference: dict[str, Any] | None = None
    child_count: int | None = None


class SharePointFolderCreateRequest(ApiSchema):
    connection_id: UUID
    name: str = Field(min_length=1, max_length=255)
    parent_item_id: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if "/" in normalized or "\\" in normalized:
            raise ValueError("Folder name cannot contain path separators.")
        return normalized


class SharePointFolderMappingWrite(ApiSchema):
    sharepoint_connection_id: UUID
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    mapping_scope: FolderMappingScope
    remote_folder_path: str = Field(min_length=1, max_length=1000)
    remote_folder_id: str | None = Field(default=None, max_length=1000)
    filename_pattern: str | None = Field(default=None, max_length=500)
    create_folder_if_missing: bool = False
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=1_000_000)

    @field_validator("remote_folder_path")
    @classmethod
    def validate_remote_path(cls, value: str) -> str:
        return _safe_remote_path(value)

    @model_validator(mode="after")
    def validate_scope_fields(self) -> SharePointFolderMappingWrite:
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
            FolderMappingScope.SECTION_DOCUMENT_TYPE: (False, True, True),
        }
        required = requirements[self.mapping_scope]
        supplied = (
            self.department_id is not None,
            self.section_id is not None,
            self.document_type_id is not None,
        )
        if supplied != required:
            raise ValueError(
                "Folder mapping identifiers must match mappingScope."
            )
        return self


class SharePointFolderMappingCreateRequest(SharePointFolderMappingWrite):
    pass


class SharePointFolderMappingUpdateRequest(
    SharePointFolderMappingWrite
):
    pass


class SharePointFolderMappingResponse(SharePointFolderMappingWrite):
    id: UUID
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SharePointFolderMappingListResponse(
    PaginationData[SharePointFolderMappingResponse]
):
    pass


class SharePointMetadataMappingWrite(ApiSchema):
    sharepoint_connection_id: UUID
    document_field: str = Field(min_length=1, max_length=255)
    sharepoint_field_internal_name: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    data_type: MetadataDataType = MetadataDataType.STRING
    direction: MetadataDirection = MetadataDirection.OUTBOUND
    is_required: bool = False
    default_value: Any = None
    transformer_code: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class SharePointMetadataMappingCreateRequest(
    SharePointMetadataMappingWrite
):
    pass


class SharePointMetadataMappingUpdateRequest(
    SharePointMetadataMappingWrite
):
    pass


class SharePointMetadataMappingResponse(
    SharePointMetadataMappingWrite
):
    id: UUID
    created_at: datetime
    updated_at: datetime


class SharePointMetadataMappingListResponse(
    PaginationData[SharePointMetadataMappingResponse]
):
    pass
