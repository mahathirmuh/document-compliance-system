"""Document-register XLSX preview and confirmation contracts."""

from enum import Enum
from typing import Any

from pydantic import Field

from app.schemas.base import ApiSchema


class DocumentImportMode(str, Enum):
    CREATE_ONLY = "CREATE_ONLY"
    CREATE_AND_ADD_REVISION = "CREATE_AND_ADD_REVISION"
    UPSERT_METADATA = "UPSERT_METADATA"


class DocumentImportRowStatus(str, Enum):
    VALID_CREATE = "VALID_CREATE"
    VALID_ADD_REVISION = "VALID_ADD_REVISION"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"
    WARNING = "WARNING"


class DocumentImportPreviewRow(ApiSchema):
    row_number: int = Field(ge=2)
    status: DocumentImportRowStatus
    base_document_code: str | None
    revision_code: str | None
    title: str | None
    department_code: str | None
    document_type_code: str | None
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentImportPreviewResponse(ApiSchema):
    total_rows: int = Field(ge=0)
    valid_create_rows: int = Field(ge=0)
    valid_add_revision_rows: int = Field(ge=0)
    warning_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    rows: list[DocumentImportPreviewRow]
    warnings: list[str] = Field(default_factory=list)


class DocumentImportConfirmRequest(ApiSchema):
    mode: DocumentImportMode = DocumentImportMode.CREATE_AND_ADD_REVISION


class DocumentImportResultResponse(ApiSchema):
    mode: DocumentImportMode
    total_rows: int = Field(ge=0)
    documents_created: int = Field(ge=0)
    revisions_added: int = Field(ge=0)
    metadata_updated: int = Field(ge=0)
    duplicates_skipped: int = Field(ge=0)
    invalid_skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
