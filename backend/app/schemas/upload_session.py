"""Upload-session preview and lifecycle response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.upload_session import UploadSessionStatus, UploadSessionType
from app.schemas.base import ApiSchema
from app.schemas.document_upload import FileIdentificationResult


class UploadSessionItemResponse(FileIdentificationResult):
    """One temporary file and its identification result."""


class UploadSessionResponse(ApiSchema):
    session_id: UUID
    session_type: UploadSessionType
    status: UploadSessionStatus
    total_files: int
    total_size: int
    expires_at: datetime
    committed_at: datetime | None = None
    cancelled_at: datetime | None = None
    items: list[UploadSessionItemResponse]


class BatchUploadResponse(UploadSessionResponse):
    """Batch preview response."""
