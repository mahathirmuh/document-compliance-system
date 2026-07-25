"""Document-register request, response, filter, parse, and bulk schemas."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.document_revision import (
    DocumentRevisionCreate,
    DocumentRevisionListItem,
    MasterDataReference,
    UserReference,
)
from app.services.documents.document_code_service import DocumentCodeService

DOCUMENT_NUMBER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")


def _required_text(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be empty.")
        return normalized
    return value


def _optional_text(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _company_code(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        return DocumentCodeService.normalize_component(
            value,
            field="companyCode",
        )
    return value


def _document_number(value: object) -> object:
    if isinstance(value, str):
        return DocumentCodeService.normalize_document_number(value)
    return value


class DocumentCreate(ApiSchema):
    company_code: str | None = Field(default=None, min_length=1, max_length=20)
    department_id: UUID
    section_id: UUID | None = None
    document_type_id: UUID
    document_number: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    owner_department_id: UUID | None = None
    document_owner_name: str | None = Field(default=None, max_length=150)
    initial_revision: DocumentRevisionCreate | None = None

    _company = field_validator("company_code", mode="before")(_company_code)
    _number = field_validator("document_number", mode="before")(
        _document_number
    )
    _title = field_validator("title", mode="before")(_required_text)
    _optional = field_validator(
        "description",
        "document_owner_name",
        mode="before",
    )(_optional_text)


class DocumentUpdate(ApiSchema):
    company_code: str | None = Field(default=None, min_length=1, max_length=20)
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    document_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    owner_department_id: UUID | None = None
    document_owner_name: str | None = Field(default=None, max_length=150)
    change_reason: str | None = Field(default=None, max_length=1000)

    _company = field_validator("company_code", mode="before")(_company_code)
    _number = field_validator("document_number", mode="before")(
        lambda value: (
            _document_number(value) if value is not None else None
        )
    )
    _title = field_validator("title", mode="before")(
        lambda value: _required_text(value) if value is not None else None
    )
    _optional = field_validator(
        "description",
        "document_owner_name",
        "change_reason",
        mode="before",
    )(_optional_text)


class DocumentArchiveRequest(ApiSchema):
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason", mode="before")(_required_text)


class DocumentRestoreRequest(ApiSchema):
    reason: str | None = Field(default=None, max_length=1000)

    _reason = field_validator("reason", mode="before")(_optional_text)


class DocumentParseRequest(ApiSchema):
    value: str = Field(min_length=1, max_length=500)

    _value = field_validator("value", mode="before")(_required_text)


class DocumentParseResponse(ApiSchema):
    company_code: str
    department: MasterDataReference
    section: MasterDataReference | None
    document_type: MasterDataReference
    document_number: str
    base_document_code: str
    revision_code: str | None
    full_document_code: str | None
    file_extension: str | None
    warnings: list[str] = Field(default_factory=list)


class DocumentFormDepartmentOption(ApiSchema):
    id: UUID
    code: str
    name: str


class DocumentFormSectionOption(DocumentFormDepartmentOption):
    department_id: UUID


class DocumentFormTypeOption(DocumentFormDepartmentOption):
    requires_section: bool
    default_validation_rule_id: UUID | None


class DocumentFormStatusOption(DocumentFormDepartmentOption):
    is_initial: bool


class DocumentFormRuleOption(DocumentFormDepartmentOption):
    document_type_id: UUID | None
    is_default: bool


class DocumentFormOptionsResponse(ApiSchema):
    default_company_code: str
    departments: list[DocumentFormDepartmentOption]
    sections: list[DocumentFormSectionOption]
    document_types: list[DocumentFormTypeOption]
    document_statuses: list[DocumentFormStatusOption]
    validation_rules: list[DocumentFormRuleOption]


class DocumentRevisionSummary(ApiSchema):
    id: UUID
    document_id: UUID
    revision_code: str
    revision_number: int | None
    full_document_code: str
    document_status_id: UUID
    validation_rule_id: UUID | None
    status: MasterDataReference
    validation_rule: MasterDataReference | None
    issue_date: date | None
    effective_date: date | None
    review_date: date | None
    expiry_date: date | None
    sharepoint_url: str | None
    external_reference: str | None
    remarks: str | None
    is_current: bool
    is_superseded: bool


class DocumentListItem(ApiSchema):
    id: UUID
    company_code: str
    department_id: UUID
    section_id: UUID | None
    document_type_id: UUID
    document_number: str
    base_document_code: str
    title: str
    department: MasterDataReference
    section: MasterDataReference | None
    document_type: MasterDataReference
    current_revision: DocumentRevisionSummary | None
    is_archived: bool
    updated_at: datetime


class DocumentResponse(DocumentListItem):
    description: str | None
    owner_department: MasterDataReference | None
    owner_department_id: UUID | None
    document_owner_name: str | None
    current_revision_id: UUID | None
    archived_at: datetime | None
    archived_by: UserReference | None
    archive_reason: str | None
    created_by: UserReference | None
    updated_by: UserReference | None
    created_at: datetime


class DocumentDetailResponse(DocumentResponse):
    revisions: list[DocumentRevisionListItem]


class DocumentListResponse(PaginationData[DocumentListItem]):
    pass


class DocumentFilter(ApiSchema):
    search: str | None = None
    base_document_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    document_status_id: UUID | None = None
    validation_rule_id: UUID | None = None
    revision_code: str | None = None
    company_code: str | None = None
    is_archived: bool = False
    has_sharepoint_url: bool | None = None
    created_by: UUID | None = None
    created_from: date | None = None
    created_to: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Literal[
        "baseDocumentCode",
        "title",
        "companyCode",
        "department",
        "documentType",
        "createdAt",
        "updatedAt",
        "effectiveDate",
    ] = "updatedAt"
    sort_order: Literal["asc", "desc"] = "desc"


class BulkDocumentIdsRequest(ApiSchema):
    document_ids: list[UUID] = Field(min_length=1, max_length=100)


class BulkArchiveRequest(BulkDocumentIdsRequest):
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason", mode="before")(_required_text)


class BulkRestoreRequest(BulkDocumentIdsRequest):
    pass


class BulkUpdateStatusRequest(BulkDocumentIdsRequest):
    document_status_id: UUID
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason", mode="before")(_required_text)


class BulkDocumentItemResult(ApiSchema):
    document_id: UUID
    success: bool
    message: str


class BulkDocumentResult(ApiSchema):
    operation: Literal["archive", "restore", "update-status"]
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    results: list[BulkDocumentItemResult]
