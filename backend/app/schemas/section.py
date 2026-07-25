"""Section request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.department import (
    normalize_description,
    normalize_name,
    normalize_strict_code,
)
from app.schemas.master_data import MasterDataOption


class SectionCreate(ApiSchema):
    department_id: UUID
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_strict_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(
        normalize_description
    )


class SectionUpdate(ApiSchema):
    department_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def validate_code(cls, value: object) -> object:
        return normalize_strict_code(value) if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        return normalize_name(value) if isinstance(value, str) else value

    _description = field_validator("description", mode="before")(
        normalize_description
    )


class SectionResponse(ApiSchema):
    id: UUID
    department_id: UUID
    department: MasterDataOption | None = None
    code: str
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SectionListResponse(PaginationData[SectionResponse]):
    pass


class SectionFilter(ApiSchema):
    department_id: UUID | None = None
    search: str | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "code"
    sort_order: str = "asc"

