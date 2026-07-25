"""Public schemas for physical document files and file history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.document_file import DocumentFileStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.document_revision import UserReference


def _required_reason(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Reason must not be empty.")
    return normalized


class DocumentFileListItem(ApiSchema):
    """Safe file metadata returned without internal storage coordinates."""

    id: UUID
    document_id: UUID
    document_revision_id: UUID
    original_filename: str
    sanitized_filename: str
    file_extension: str
    mime_type: str
    detected_mime_type: str
    file_size: int = Field(ge=0)
    sha256_hash: str
    storage_provider: str
    file_status: DocumentFileStatus
    is_primary: bool
    is_current: bool
    uploaded_by: UserReference | None
    uploaded_at: datetime
    replaced_at: datetime | None = None
    replaced_by_file_id: UUID | None = None
    deleted_at: datetime | None = None
    deletion_reason: str | None = None
    base_document_code: str
    document_title: str
    revision_code: str
    full_document_code: str


class DocumentFileResponse(DocumentFileListItem):
    """Alias retained for callers expecting a singular file response."""


class DocumentFileDetailResponse(DocumentFileListItem):
    """Detailed metadata; storage key and server paths remain private."""

    deleted_by: UserReference | None = None
    metadata: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime


class DocumentFileDeleteRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason", mode="before")(_required_reason)


class DocumentFileRestoreRequest(ApiSchema):
    reason: str | None = Field(default=None, max_length=1000)
    replace_current: bool = False

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class DocumentFileReplaceRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason", mode="before")(_required_reason)


class DocumentFileListResponse(PaginationData[DocumentFileListItem]):
    """Paginated upload history."""

