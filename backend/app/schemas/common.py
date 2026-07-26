"""Shared API response schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")
ItemT = TypeVar("ItemT")


class ErrorDetail(BaseModel):
    """One client-safe validation or business error."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    message: str
    code: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]*$",
        exclude_if=lambda value: value is None,
    )


class ApiResponse(BaseModel, Generic[DataT]):
    """Consistent response envelope used by every API endpoint."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    data: DataT | None
    errors: list[ErrorDetail] | None = None


class PaginationData(BaseModel, Generic[ItemT]):
    """Reusable pagination payload for list endpoints in later phases."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[ItemT]
    page: int = Field(ge=1)
    page_size: int = Field(alias="pageSize", ge=1)
    total_items: int = Field(alias="totalItems", ge=0)
    total_pages: int = Field(alias="totalPages", ge=0)
