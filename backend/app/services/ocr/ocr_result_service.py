"""Department-scoped OCR result, page, block, and history reads."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, has_permission
from app.core.config import Settings
from app.models.document_file import DocumentFileStatus
from app.models.ocr_page_result import OCRPageResult, OCRPageStatus
from app.models.ocr_run import OCRRun
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_page_result_repository import (
    OCRPageResultRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.extraction_job import (
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)
from app.schemas.ocr import (
    OCRBlockListResponse,
    OCRBlockResponse,
    OCRJobError,
    OCRPageDetailResponse,
    OCRPageListResponse,
    OCRPageResultResponse,
    OCRRunHistoryItem,
    OCRRunHistoryResponse,
    OCRRunResponse,
    OCRSummary,
)
from app.schemas.ocr_internal import OCRBoundingBox
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import DocumentServiceBase
from app.services.ocr.ocr_job_service import ocr_run_not_found


class OCRResultService(DocumentServiceBase):
    """Read OCR results without exposing storage or temporary paths."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.runs = OCRRunRepository(session)
        self.pages = OCRPageResultRepository(session)
        self.blocks = OCRBlockRepository(session)
        self.files = DocumentFileRepository(session)

    async def latest_for_file(self, file_id: UUID) -> OCRRunResponse:
        document_file = await self.files.get_by_id(file_id)
        if document_file is None:
            raise ocr_run_not_found()
        try:
            self.policy.ensure_document_access(document_file.document)
        except Exception as exc:
            raise ocr_run_not_found() from exc
        if (
            document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
        ):
            raise ocr_run_not_found()
        run = await self.runs.get_latest_by_file(file_id)
        self._ensure_run_access(run, history=False)
        assert run is not None
        return ocr_run_response(
            run,
            **(await self._summary_options([run.id]))[run.id],
        )

    async def get_run(self, run_id: UUID) -> OCRRunResponse:
        run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(run, history=False)
        assert run is not None
        return ocr_run_response(
            run,
            **(await self._summary_options([run.id]))[run.id],
        )

    async def history_for_file(
        self,
        file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> OCRRunHistoryResponse:
        self._ensure_history_permission()
        document_file = await self.files.get_by_id(file_id)
        if document_file is None:
            raise ocr_run_not_found()
        try:
            self.policy.ensure_document_access(document_file.document)
        except Exception as exc:
            raise ocr_run_not_found() from exc
        runs = await self.runs.list_by_file(
            file_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        total = await self.runs.count_by_file(file_id)
        summary_options = await self._summary_options(
            [run.id for run in runs]
        )
        return OCRRunHistoryResponse(
            items=[
                ocr_run_history_item(
                    run,
                    **summary_options[run.id],
                )
                for run in runs
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_pages(
        self,
        run_id: UUID,
        *,
        statuses: list[OCRPageStatus] | None,
        page: int,
        page_size: int,
    ) -> OCRPageListResponse:
        run = await self._accessible_run(run_id)
        items, total = await self.pages.list_by_run(
            run.id,
            statuses=statuses,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return OCRPageListResponse(
            items=[ocr_page_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def get_page(
        self,
        run_id: UUID,
        page_number: int,
    ) -> OCRPageDetailResponse:
        run = await self._accessible_run(run_id)
        page = await self.pages.get_by_run_and_page(
            run.id,
            page_number,
        )
        if page is None:
            raise ocr_run_not_found()
        blocks = await self.blocks.list_for_page(page.id)
        return OCRPageDetailResponse(
            page=ocr_page_response(page),
            blocks=[ocr_block_response(block, page.page_number) for block in blocks],
        )

    async def list_blocks(
        self,
        run_id: UUID,
        *,
        page_number: int | None,
        minimum_confidence: float | None,
        maximum_confidence: float | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> OCRBlockListResponse:
        run = await self._accessible_run(run_id)
        if (
            minimum_confidence is not None
            and maximum_confidence is not None
            and minimum_confidence > maximum_confidence
        ):
            from app.services.documents.base import document_error

            raise document_error(
                "Minimum confidence cannot exceed maximum confidence.",
                field="minimumConfidence",
                title="OCR confidence filter is invalid.",
            )
        rows, total = await self.blocks.list_by_run(
            run.id,
            page_number=page_number,
            minimum_confidence=minimum_confidence,
            maximum_confidence=maximum_confidence,
            search=search,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return OCRBlockListResponse(
            items=[ocr_block_response(block, block_page) for block, block_page in rows],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def _accessible_run(self, run_id: UUID) -> OCRRun:
        run = await self.runs.get_by_id(run_id)
        self._ensure_run_access(run, history=False)
        assert run is not None
        return run

    def _ensure_run_access(
        self,
        run: OCRRun | None,
        *,
        history: bool,
    ) -> None:
        if run is None:
            raise ocr_run_not_found()
        try:
            self.policy.ensure_document_access(run.document)
        except Exception as exc:
            raise ocr_run_not_found() from exc
        can_view_history = has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_OCR_HISTORY,
            is_superuser=self.user.is_superuser,
        )
        if history and not can_view_history:
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError()
        if can_view_history:
            return
        latest_id = getattr(
            run.document_file,
            "latest_ocr_run_id",
            None,
        )
        if (
            run.document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not run.document_file.is_current
            or latest_id != run.id
        ):
            raise ocr_run_not_found()

    def _ensure_history_permission(self) -> None:
        if not has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_OCR_HISTORY,
            is_superuser=self.user.is_superuser,
        ):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError()

    async def _summary_options(
        self,
        run_ids: list[UUID],
    ) -> dict[UUID, dict[str, float | int]]:
        low_threshold = float(
            getattr(self.settings, "ocr_low_confidence_threshold", 0.60)
        )
        review_threshold = float(
            getattr(self.settings, "ocr_review_confidence_threshold", 0.80)
        )
        counts = await self.blocks.count_below_confidence_by_run(
            run_ids,
            threshold=low_threshold,
        )
        return {
            run_id: {
                "low_confidence_blocks": counts.get(run_id, 0),
                "low_confidence_threshold": low_threshold,
                "review_confidence_threshold": review_threshold,
            }
            for run_id in run_ids
        }


def _warnings(run: OCRRun) -> list[str]:
    return [
        warning
        if isinstance(warning, str)
        else str(warning.get("message") or warning.get("code") or "OCR_WARNING")
        for warning in run.warnings_json
    ]


def ocr_summary(
    run: OCRRun,
    *,
    low_confidence_blocks: int = 0,
    low_confidence_threshold: float = 0.60,
    review_confidence_threshold: float = 0.80,
) -> OCRSummary:
    return OCRSummary(
        run_id=run.id,
        status=run.status,
        page_count_requested=run.page_count_requested,
        page_count_processed=run.page_count_processed,
        page_count_failed=run.page_count_failed,
        total_blocks=run.total_blocks,
        total_characters=run.total_characters,
        average_confidence=run.average_confidence,
        minimum_confidence=run.minimum_confidence,
        maximum_confidence=run.maximum_confidence,
        low_confidence_blocks=low_confidence_blocks,
        low_confidence_threshold=low_confidence_threshold,
        review_confidence_threshold=review_confidence_threshold,
        warnings=_warnings(run),
    )


def ocr_run_response(
    run: OCRRun,
    *,
    low_confidence_blocks: int = 0,
    low_confidence_threshold: float = 0.60,
    review_confidence_threshold: float = 0.80,
) -> OCRRunResponse:
    summary = ocr_summary(
        run,
        low_confidence_blocks=low_confidence_blocks,
        low_confidence_threshold=low_confidence_threshold,
        review_confidence_threshold=review_confidence_threshold,
    )
    return OCRRunResponse(
        **summary.model_dump(),
        ocr_job_id=run.ocr_job_id,
        source_extraction_run_id=run.source_extraction_run_id,
        document=ExtractionDocumentReference(
            id=run.document.id,
            base_document_code=run.document.base_document_code,
            title=run.document.title,
            department_id=run.document.department_id,
        ),
        revision=ExtractionRevisionReference(
            id=run.revision.id,
            revision_code=run.revision.revision_code,
            full_document_code=run.revision.full_document_code,
        ),
        file=ExtractionFileReference(
            id=run.document_file.id,
            filename=run.document_file.original_filename,
            extension=run.document_file.file_extension,
            sha256_hash=run.document_file.sha256_hash,
        ),
        provider=run.provider,
        provider_version=run.provider_version,
        language_profile=run.language_profile,
        source_sha256_hash=run.source_sha256_hash,
        render_dpi=run.render_dpi,
        preprocessing_profile=run.preprocessing_profile,
        content_hash=run.content_hash,
        metadata=run.metadata_json,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        is_latest=(
            getattr(
                run.document_file,
                "latest_ocr_run_id",
                None,
            )
            == run.id
        ),
    )


def ocr_run_history_item(
    run: OCRRun,
    *,
    low_confidence_blocks: int = 0,
    low_confidence_threshold: float = 0.60,
    review_confidence_threshold: float = 0.80,
) -> OCRRunHistoryItem:
    return OCRRunHistoryItem(
        id=run.id,
        ocr_job_id=run.ocr_job_id,
        source_extraction_run_id=run.source_extraction_run_id,
        status=run.status,
        provider=run.provider,
        provider_version=run.provider_version,
        language_profile=run.language_profile,
        preprocessing_profile=run.preprocessing_profile,
        summary=ocr_summary(
            run,
            low_confidence_blocks=low_confidence_blocks,
            low_confidence_threshold=low_confidence_threshold,
            review_confidence_threshold=review_confidence_threshold,
        ),
        requested_by=(
            ExtractionRequesterReference(
                id=run.ocr_job.requester.id,
                name=run.ocr_job.requester.name,
            )
            if run.ocr_job.requester is not None
            else None
        ),
        re_ocr_reason=(
            (run.ocr_job.result_summary_json or {}).get("reOcrReason")
            if isinstance(
                (run.ocr_job.result_summary_json or {}).get("reOcrReason"),
                str,
            )
            else None
        ),
        completed_at=run.completed_at,
        created_at=run.created_at,
        is_latest=(
            getattr(
                run.document_file,
                "latest_ocr_run_id",
                None,
            )
            == run.id
        ),
    )


def ocr_page_response(page: OCRPageResult) -> OCRPageResultResponse:
    return OCRPageResultResponse(
        id=page.id,
        ocr_run_id=page.ocr_run_id,
        page_number=page.page_number,
        status=page.status,
        language_profile=page.language_profile,
        render_width=page.render_width,
        render_height=page.render_height,
        render_dpi=page.render_dpi,
        rotation_applied=page.rotation_applied,
        deskew_angle=page.deskew_angle,
        block_count=page.block_count,
        character_count=page.character_count,
        average_confidence=page.average_confidence,
        minimum_confidence=page.minimum_confidence,
        maximum_confidence=page.maximum_confidence,
        raw_text=page.raw_text,
        normalised_text=page.normalised_text,
        content_hash=page.content_hash,
        warning_codes=page.warning_codes_json,
        error=(
            OCRJobError(
                code=page.error_code,
                message=page.error_message or "OCR page processing failed.",
            )
            if page.error_code is not None
            else None
        ),
        metadata=page.metadata_json,
        created_at=page.created_at,
    )


def ocr_block_response(
    block: object,
    page_number: int,
) -> OCRBlockResponse:
    from app.models.ocr_block import OCRBlock

    if not isinstance(block, OCRBlock):
        raise TypeError("Expected an OCRBlock model.")
    bbox = block.bbox_json
    return OCRBlockResponse(
        id=block.id,
        ocr_run_id=block.ocr_run_id,
        ocr_page_result_id=block.ocr_page_result_id,
        page_number=page_number,
        block_order=block.block_order,
        text=block.text,
        normalised_text=block.normalised_text,
        confidence=block.confidence,
        polygon=block.polygon_json,
        bbox=OCRBoundingBox(
            x=float(bbox.get("x", 0)),
            y=float(bbox.get("y", 0)),
            width=float(bbox.get("width", 0)),
            height=float(bbox.get("height", 0)),
        ),
        provider_model=block.provider_model,
        recognition_profile=block.recognition_profile,
        orientation=block.orientation,
        metadata=block.metadata_json,
        character_count=block.character_count,
        created_at=block.created_at,
    )
