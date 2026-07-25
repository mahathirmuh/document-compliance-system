"""Department request and response schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData

STRICT_CODE = re.compile(r"^[A-Z0-9_]+$")


def normalize_strict_code(value: str) -> str:
    normalized = value.strip().upper()
    if not STRICT_CODE.fullmatch(normalized):
        raise ValueError(
            "Code may contain only A-Z, 0-9, and underscore."
        )
    return normalized


def normalize_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Name must not be empty.")
    return normalized


def normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class DepartmentCreate(ApiSchema):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True

    _code = field_validator("code", mode="before")(normalize_strict_code)
    _name = field_validator("name", mode="before")(normalize_name)
    _description = field_validator("description", mode="before")(
        normalize_description
    )


class DepartmentUpdate(ApiSchema):
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


class DepartmentResponse(ApiSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DepartmentListResponse(PaginationData[DepartmentResponse]):
    pass


class DepartmentFilter(ApiSchema):
    search: str | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "code"
    sort_order: str = "asc"

