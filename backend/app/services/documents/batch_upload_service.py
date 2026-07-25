"""Explicit batch façade over the shared two-stage upload engine."""

from fastapi import UploadFile

from app.schemas.document_upload import (
    BatchUploadConfirmationRequest,
    BatchUploadResult,
)
from app.schemas.upload_session import BatchUploadResponse
from app.services.documents.document_upload_service import (
    DocumentUploadService,
)


class BatchUploadService(DocumentUploadService):
    """Keep batch endpoints small while sharing validation and compensation."""

    async def preview(self, uploads: list[UploadFile]) -> BatchUploadResponse:
        return await self.preview_batch(uploads)

    async def confirm_preview(
        self,
        session_id,
        payload: BatchUploadConfirmationRequest,
    ) -> BatchUploadResult:
        return await self.confirm_batch(session_id, payload)

