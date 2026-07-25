"""Document-type request and response schemas."""

import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.department import normalize_description, normalize_name
from app.schemas.master_data import MasterDataOption

FLEXIBLE_CODE = re.compile(r"^[A-Z0-9_-]+$")


def normalize_flexible_code(value: str) -> str:
    normalized = value.strip().upper()
    if not FLEXIBLE_CODE.fullmatch(normalized):
        raise ValueError(
            "Code may contain only A-Z, 0-9, underscore, and hyphen."
        )
    return normalized


class DocumentTypeCategory(str, Enum):
    PROCEDURE = "PROCEDURE"
    POLICY = "POLICY"
    GUIDELINE = "GUIDELINE"
    FORM = "FORM"
    MANUAL = "MANUAL"
    PLAN = "PLAN"
    OTHER = "OTHER"


class DocumentTypeCreate(ApiSchema):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    category: DocumentTypeCategory | None = None
    description: str | None = None
    requires_section: bool = True
    default_validation_rule_id: UUID | None = None
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_flexible_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(
        normalize_description
    )


class DocumentTypeUpdate(ApiSchema):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: DocumentTypeCategory | None = None
    description: str | None = None
    requires_section: bool | None = None
    default_validation_rule_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def validate_code(cls, value: object) -> object:
        return normalize_flexible_code(value) if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        return normalize_name(value) if isinstance(value, str) else value

    _description = field_validator("description", mode="before")(
        normalize_description
    )


class DocumentTypeResponse(ApiSchema):
    id: UUID
    code: str
    name: str
    category: DocumentTypeCategory | None
    description: str | None
    requires_section: bool
    default_validation_rule_id: UUID | None
    default_validation_rule: MasterDataOption | None = None
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentTypeListResponse(PaginationData[DocumentTypeResponse]):
    pass


class DocumentTypeFilter(ApiSchema):
    search: str | None = None
    category: DocumentTypeCategory | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "code"
    sort_order: str = "asc"

