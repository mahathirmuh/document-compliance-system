"""Schemas for upload preview, identification, and confirmation."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
    UploadSessionItemStatus,
)
from app.schemas.base import ApiSchema


class ParsedDocumentMetadata(ApiSchema):
    company_code: str | None = None
    department_code: str | None = None
    section_code: str | None = None
    document_type_code: str | None = None
    document_number: str | None = None
    title: str | None = Field(default=None, max_length=500)
    revision_code: str | None = None
    base_document_code: str | None = None
    full_document_code: str | None = None


class MatchedDocumentReference(ApiSchema):
    id: UUID
    base_document_code: str
    title: str


class MatchedRevisionReference(ApiSchema):
    id: UUID
    revision_code: str
    full_document_code: str


class FileDuplicateWarning(ApiSchema):
    message: str = "Duplicate file already exists."
    same_revision: bool = False
    document_id: UUID | None = None
    revision_id: UUID | None = None
    base_document_code: str | None = None


class FileIdentificationResult(ApiSchema):
    upload_item_id: UUID
    original_filename: str
    sanitized_filename: str
    file_extension: str | None = None
    mime_type: str | None = None
    detected_mime_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    sha256_hash: str | None = None
    identification_status: UploadIdentificationStatus
    proposed_action: UploadProposedAction
    parsed_metadata: ParsedDocumentMetadata | None = None
    matched_document: MatchedDocumentReference | None = None
    matched_revision: MatchedRevisionReference | None = None
    duplicate_warning: FileDuplicateWarning | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    quarantine_reason: str | None = None
    status: UploadSessionItemStatus


class UploadActionMetadata(ApiSchema):
    """Union-shaped metadata validated again for the selected action."""

    company_code: str | None = Field(default=None, max_length=20)
    department_id: UUID | None = None
    section_id: UUID | None = None
    document_type_id: UUID | None = None
    document_number: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    revision_code: str | None = Field(default=None, max_length=30)
    document_status_id: UUID | None = None
    validation_rule_id: UUID | None = None
    issue_date: date | None = None
    effective_date: date | None = None
    review_date: date | None = None
    expiry_date: date | None = None
    sharepoint_url: HttpUrl | None = None
    external_reference: str | None = Field(default=None, max_length=500)
    remarks: str | None = None
    set_as_current_revision: bool = True
    reason: str | None = Field(default=None, max_length=1000)
    allow_duplicate: bool = False


class UploadConfirmationItem(ApiSchema):
    upload_item_id: UUID
    action: UploadProposedAction
    document_id: UUID | None = None
    revision_id: UUID | None = None
    metadata: UploadActionMetadata | None = None

    @model_validator(mode="after")
    def validate_action_targets(self) -> UploadConfirmationItem:
        if self.action == UploadProposedAction.ATTACH_TO_EXISTING_REVISION:
            if self.document_id is None or self.revision_id is None:
                raise ValueError(
                    "documentId and revisionId are required when attaching "
                    "to an existing revision."
                )
        elif self.action == UploadProposedAction.CREATE_DOCUMENT_AND_REVISION:
            if self.metadata is None:
                raise ValueError(
                    "metadata is required when creating a document."
                )
            required = {
                "departmentId": self.metadata.department_id,
                "documentTypeId": self.metadata.document_type_id,
                "documentNumber": self.metadata.document_number,
                "title": self.metadata.title,
                "revisionCode": self.metadata.revision_code,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required when creating a document."
                )
        elif self.action == UploadProposedAction.ADD_NEW_REVISION:
            if self.document_id is None:
                raise ValueError(
                    "documentId is required when adding a revision."
                )
            if self.metadata is None or not self.metadata.revision_code:
                raise ValueError(
                    "metadata.revisionCode is required when adding a revision."
                )
        elif self.action == UploadProposedAction.REPLACE_CURRENT_FILE:
            if self.document_id is None or self.revision_id is None:
                raise ValueError(
                    "documentId and revisionId are required when replacing a "
                    "file."
                )
            if self.metadata is None or not (
                self.metadata.reason and self.metadata.reason.strip()
            ):
                raise ValueError(
                    "metadata.reason is required when replacing a file."
                )
        return self


class UploadConfirmationRequest(ApiSchema):
    items: list[UploadConfirmationItem] = Field(
        min_length=1,
        max_length=500,
    )


class UploadConfirmationItemResult(ApiSchema):
    upload_item_id: UUID
    action: UploadProposedAction
    status: UploadSessionItemStatus
    document_id: UUID | None = None
    revision_id: UUID | None = None
    document_file_id: UUID | None = None
    base_document_code: str | None = None
    revision_code: str | None = None
    file_status: str | None = None
    error: str | None = None


class UploadConfirmationResult(ApiSchema):
    session_id: UUID
    status: str
    items: list[UploadConfirmationItemResult]


class BatchUploadConfirmationRequest(UploadConfirmationRequest):
    """Batch confirmation has the same item contract."""


class BatchUploadResult(ApiSchema):
    session_id: UUID
    status: str
    total: int = Field(ge=0)
    committed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    documents_created: int = Field(ge=0)
    revisions_created: int = Field(ge=0)
    files_attached: int = Field(ge=0)
    files_replaced: int = Field(ge=0)
    items: list[UploadConfirmationItemResult]
    committed_at: datetime | None = None
