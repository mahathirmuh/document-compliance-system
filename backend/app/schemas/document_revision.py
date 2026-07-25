"""Document-revision request and response contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, HttpUrl, TypeAdapter, field_validator, model_validator

from app.schemas.base import ApiSchema
from app.services.documents.document_code_service import DocumentCodeService


def _optional_text(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return value


def _optional_url(value: object) -> object:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    return str(TypeAdapter(HttpUrl).validate_python(normalized))


class MasterDataReference(ApiSchema):
    id: UUID
    code: str
    name: str


class UserReference(ApiSchema):
    id: UUID
    name: str


class DocumentRevisionCreate(ApiSchema):
    revision_code: str = Field(min_length=1, max_length=30)
    document_status_id: UUID | None = None
    validation_rule_id: UUID | None = None
    issue_date: date | None = None
    effective_date: date | None = None
    review_date: date | None = None
    expiry_date: date | None = None
    sharepoint_url: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=500)
    remarks: str | None = None
    set_as_current: bool = True

    @field_validator("revision_code", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> object:
        if isinstance(value, str):
            return DocumentCodeService.normalize_revision_code(value)
        return value

    _url = field_validator("sharepoint_url", mode="before")(_optional_url)
    _optional_fields = field_validator(
        "external_reference",
        "remarks",
        mode="before",
    )(_optional_text)

    @model_validator(mode="after")
    def validate_dates(self) -> DocumentRevisionCreate:
        if (
            self.effective_date is not None
            and self.expiry_date is not None
            and self.expiry_date < self.effective_date
        ):
            raise ValueError(
                "expiryDate must not be before effectiveDate."
            )
        if (
            self.issue_date is not None
            and self.review_date is not None
            and self.review_date < self.issue_date
        ):
            raise ValueError("reviewDate must not be before issueDate.")
        return self


class DocumentRevisionUpdate(ApiSchema):
    revision_code: str | None = Field(default=None, min_length=1, max_length=30)
    document_status_id: UUID | None = None
    validation_rule_id: UUID | None = None
    issue_date: date | None = None
    effective_date: date | None = None
    review_date: date | None = None
    expiry_date: date | None = None
    sharepoint_url: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=500)
    remarks: str | None = None
    change_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("revision_code", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> object:
        if isinstance(value, str):
            return DocumentCodeService.normalize_revision_code(value)
        return value

    _url = field_validator("sharepoint_url", mode="before")(_optional_url)
    _optional_fields = field_validator(
        "external_reference",
        "remarks",
        "change_reason",
        mode="before",
    )(_optional_text)


class DocumentRevisionSetCurrentRequest(ApiSchema):
    reason: str | None = Field(default=None, max_length=1000)

    _reason = field_validator("reason", mode="before")(_optional_text)


class DocumentRevisionSupersedeRequest(ApiSchema):
    superseded_by_revision_id: UUID
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("reason must not be empty.")
            return normalized
        return value


class DocumentRevisionListItem(ApiSchema):
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
    superseded_at: datetime | None
    superseded_by_revision_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentRevisionResponse(DocumentRevisionListItem):
    created_by: UserReference | None
    updated_by: UserReference | None
