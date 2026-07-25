"""Shared schemas for master-data APIs and XLSX workflows."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import ApiSchema


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class ImportEntityType(str, Enum):
    DEPARTMENTS = "departments"
    SECTIONS = "sections"
    DOCUMENT_TYPES = "document-types"
    DOCUMENT_STATUSES = "document-statuses"
    VALIDATION_RULES = "validation-rules"


class ImportMode(str, Enum):
    CREATE_ONLY = "CREATE_ONLY"
    UPSERT = "UPSERT"


class ImportRowStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"


class MasterDataOption(ApiSchema):
    id: UUID
    code: str
    name: str
    is_active: bool


class MasterDataCount(ApiSchema):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)


class MasterDataOverview(ApiSchema):
    departments: MasterDataCount
    sections: MasterDataCount
    document_types: MasterDataCount
    document_statuses: MasterDataCount
    validation_rules: MasterDataCount


class ImportPreviewRow(ApiSchema):
    row_number: int = Field(ge=2)
    status: ImportRowStatus
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ImportPreviewResponse(ApiSchema):
    entity_type: ImportEntityType
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    rows: list[ImportPreviewRow]
    warnings: list[str] = Field(default_factory=list)


class ImportConfirmResponse(ApiSchema):
    entity_type: ImportEntityType
    mode: ImportMode
    total_rows: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)

