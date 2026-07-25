"""Department-scoped document inventory for the language workspace."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, has_permission
from app.core.exceptions import AuthorizationError
from app.models.extraction_run import ExtractionRunStatus
from app.models.language_detection_job import LanguageDetectionJobStatus
from app.models.ocr_run import OCRRunStatus
from app.models.user import User
from app.repositories.language_detection_document_repository import (
    LanguageDetectionDocumentRepository,
    LanguageDetectionDocumentRow,
)
from app.schemas.language_detection import (
    LanguageDetectionDocumentListItem,
    LanguageDetectionDocumentListResponse,
    LanguageDetectionDocumentStatus,
    LanguageJobDocumentReference,
    LanguageJobFileReference,
    LanguageJobRevisionReference,
    LanguagePresenceResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import DocumentServiceBase


class LanguageDetectionDocumentService(DocumentServiceBase):
    """List every eligible current file, including files without a job."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.documents = LanguageDetectionDocumentRepository(session)

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        status: LanguageDetectionDocumentStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> LanguageDetectionDocumentListResponse:
        self._ensure_view_permission()
        job_status = (
            LanguageDetectionJobStatus(status.value)
            if status is not None
            and status is not LanguageDetectionDocumentStatus.NOT_STARTED
            else None
        )
        rows, total = await self.documents.list(
            search=search,
            department_id=department_id,
            language_status=job_status,
            not_started=(
                status is LanguageDetectionDocumentStatus.NOT_STARTED
            ),
            scope_all_departments=self.policy.view_all_departments,
            scope_department_id=self.policy.scope_department_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return LanguageDetectionDocumentListResponse(
            items=[self._item(row) for row in rows],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    @staticmethod
    def _item(
        row: LanguageDetectionDocumentRow,
    ) -> LanguageDetectionDocumentListItem:
        document_file = row.document_file
        extraction_run = document_file.latest_extraction_run
        candidate_ocr = document_file.latest_ocr_run
        ocr_run = (
            candidate_ocr
            if extraction_run is not None
            and candidate_ocr is not None
            and candidate_ocr.source_extraction_run_id == extraction_run.id
            and candidate_ocr.status
            in {
                OCRRunStatus.COMPLETED,
                OCRRunStatus.PARTIALLY_COMPLETED,
            }
            else None
        )
        has_usable_ocr_run = ocr_run is not None
        extraction_state_ready = extraction_run is not None and (
            extraction_run.status
            in {
                ExtractionRunStatus.COMPLETED,
                ExtractionRunStatus.PARTIALLY_COMPLETED,
            }
            or (
                extraction_run.status is ExtractionRunStatus.OCR_REQUIRED
                and has_usable_ocr_run
            )
        )
        source_ready = (
            extraction_state_ready
            and (
                row.native_block_count > 0
                or (
                    has_usable_ocr_run
                    and row.ocr_block_count > 0
                )
            )
        )
        latest_run = document_file.latest_language_detection_run
        language_presence: LanguagePresenceResponse | None = None
        if latest_run is not None:
            metadata = latest_run.metadata_json or {}
            raw_coverage = metadata.get("coverage")
            coverage = (
                raw_coverage if isinstance(raw_coverage, dict) else {}
            )
            raw_presence = coverage.get("languagePresence")
            language_presence = LanguagePresenceResponse.model_validate(
                raw_presence
                if isinstance(raw_presence, dict)
                else {
                    "id": "INSUFFICIENT_EVIDENCE",
                    "en": "INSUFFICIENT_EVIDENCE",
                    "zh": "INSUFFICIENT_EVIDENCE",
                }
            )
        return LanguageDetectionDocumentListItem(
            document=LanguageJobDocumentReference(
                id=document_file.document.id,
                base_document_code=(
                    document_file.document.base_document_code
                ),
                title=document_file.document.title,
                department_id=document_file.document.department_id,
            ),
            revision=LanguageJobRevisionReference(
                id=document_file.revision.id,
                revision_code=document_file.revision.revision_code,
                full_document_code=(
                    document_file.revision.full_document_code
                ),
            ),
            file=LanguageJobFileReference(
                id=document_file.id,
                filename=document_file.original_filename,
                extension=document_file.file_extension,
                sha256_hash=document_file.sha256_hash,
            ),
            extraction_status=row.extraction_status,
            ocr_status=row.ocr_status,
            language_detection_status=row.language_status,
            language_progress=row.language_progress,
            language_current_stage=row.language_current_stage,
            extraction_run_id=(
                extraction_run.id if extraction_run is not None else None
            ),
            ocr_run_id=ocr_run.id if ocr_run is not None else None,
            language_detection_run_id=(
                latest_run.id if latest_run is not None else None
            ),
            language_presence=language_presence,
            last_detected=(
                latest_run.completed_at
                if latest_run is not None
                else None
            ),
            source_ready=source_ready and not row.language_active,
        )

    def _ensure_view_permission(self) -> None:
        if not any(
            has_permission(
                self.user.role,
                permission,
                is_superuser=self.user.is_superuser,
            )
            for permission in (
                Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                Permission.DOCUMENTS_DETECT_LANGUAGE,
            )
        ):
            raise AuthorizationError()
