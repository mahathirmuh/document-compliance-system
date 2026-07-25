"""Document-status request and response schemas."""

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


class DocumentStatusCreate(ApiSchema):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_initial: bool = False
    is_final: bool = False
    is_obsolete: bool = False
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_strict_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(
        normalize_description
    )


class DocumentStatusUpdate(ApiSchema):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_initial: bool | None = None
    is_final: bool | None = None
    is_obsolete: bool | None = None
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


class DocumentStatusResponse(ApiSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    display_order: int
    is_initial: bool
    is_final: bool
    is_obsolete: bool
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentStatusListResponse(PaginationData[DocumentStatusResponse]):
    pass


class DocumentStatusFilter(ApiSchema):
    search: str | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "displayOrder"
    sort_order: str = "asc"

