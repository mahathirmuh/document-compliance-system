"""Transactional per-page persistence and immutable OCR run finalization."""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_file import DocumentFile
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import OCRJob, OCRJobStatus
from app.models.ocr_page_result import OCRPageResult, OCRPageStatus
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_job_repository import OCRJobRepository
from app.repositories.ocr_page_result_repository import (
    OCRPageResultRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.ocr_internal import OCRPageResult as OCRPageData
from app.services.ocr.ocr_source_chain_service import OCRSourceChainService


class OCRPersistenceService:
    """Persist page checkpoints and finalize only the new OCR run."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        block_batch_size: int = 1000,
        low_confidence_threshold: float = 0.60,
        review_confidence_threshold: float = 0.80,
    ) -> None:
        self.session = session
        self.block_batch_size = block_batch_size
        self.low_confidence_threshold = low_confidence_threshold
        self.review_confidence_threshold = review_confidence_threshold
        self.jobs = OCRJobRepository(session)
        self.runs = OCRRunRepository(session)
        self.pages = OCRPageResultRepository(session)
        self.blocks = OCRBlockRepository(session)

    async def create_or_get_run(
        self,
        *,
        job: OCRJob,
        document_file: DocumentFile,
        provider_version: str | None,
        render_dpi: int,
        started_at: datetime,
    ) -> OCRRun:
        existing = await self.runs.get_by_job_id(job.id)
        if existing is not None:
            return existing
        request_metadata = dict(job.result_summary_json or {})
        run = OCRRun(
            ocr_job_id=job.id,
            document_id=job.document_id,
            document_revision_id=job.document_revision_id,
            document_file_id=job.document_file_id,
            source_extraction_run_id=job.extraction_run_id,
            provider=job.provider,
            provider_version=provider_version,
            language_profile=job.language_profile,
            status=OCRRunStatus.FAILED,
            source_sha256_hash=document_file.sha256_hash,
            page_count_requested=len(job.requested_page_numbers_json),
            page_count_processed=0,
            page_count_failed=0,
            total_blocks=0,
            total_characters=0,
            render_dpi=render_dpi,
            preprocessing_profile=job.preprocessing_profile,
            warnings_json=[],
            metadata_json={
                **request_metadata,
                "requestedPageNumbers": job.requested_page_numbers_json,
            },
            started_at=started_at,
        )
        await self.runs.create(run)
        return run

    async def persist_page(
        self,
        run: OCRRun,
        result: OCRPageData,
    ) -> OCRPageResult:
        existing = await self.pages.get_by_run_and_page(
            run.id,
            result.page_number,
        )
        if existing is not None:
            return existing
        confidences = [block.confidence for block in result.blocks]
        raw_text = result.raw_text
        normalised_text = result.normalised_text
        page = OCRPageResult(
            ocr_run_id=run.id,
            page_number=result.page_number,
            status=result.status,
            language_profile=result.language_profile,
            render_width=result.render_width,
            render_height=result.render_height,
            render_dpi=result.render_dpi,
            rotation_applied=result.rotation_applied,
            deskew_angle=result.deskew_angle,
            block_count=len(result.blocks),
            character_count=sum(len(block.normalised_text) for block in result.blocks),
            average_confidence=(
                sum(confidences) / len(confidences) if confidences else None
            ),
            minimum_confidence=min(confidences) if confidences else None,
            maximum_confidence=max(confidences) if confidences else None,
            raw_text=raw_text,
            normalised_text=normalised_text,
            content_hash=hashlib.sha256(normalised_text.encode("utf-8")).hexdigest(),
            warning_codes_json=result.warning_codes,
            error_code=result.error_code,
            error_message=result.error_message,
            metadata_json=result.metadata,
        )
        await self.pages.create(page)
        await self.blocks.batch_insert(
            (
                {
                    "ocr_run_id": run.id,
                    "ocr_page_result_id": page.id,
                    "block_order": block_order,
                    "text": block.text,
                    "normalised_text": block.normalised_text,
                    "confidence": block.confidence,
                    "polygon_json": block.polygon,
                    "bbox_json": block.bbox.model_dump(),
                    "provider_model": block.provider_model,
                    "recognition_profile": (block.recognition_profile.value),
                    "orientation": block.orientation,
                    "metadata_json": block.metadata,
                    "character_count": len(block.normalised_text),
                }
                for block_order, block in enumerate(result.blocks)
            ),
            batch_size=self.block_batch_size,
        )
        return page

    async def finalize(
        self,
        *,
        job: OCRJob,
        run: OCRRun,
        completed_at: datetime,
        cancelled: bool = False,
        terminal_failure: bool = False,
    ) -> OCRRun:
        page_rows = list(
            await self.session.scalars(
                select(OCRPageResult)
                .where(OCRPageResult.ocr_run_id == run.id)
                .order_by(OCRPageResult.page_number)
            )
        )
        confidence_rows = list(
            await self.session.scalars(
                select(OCRBlock.confidence).where(OCRBlock.ocr_run_id == run.id)
            )
        )
        failed_pages = [
            page.page_number
            for page in page_rows
            if page.status is OCRPageStatus.FAILED
        ]
        processed_pages = [
            page.page_number
            for page in page_rows
            if page.status is not OCRPageStatus.FAILED
        ]
        persisted_page_numbers = {page.page_number for page in page_rows}
        unpersisted_pages = [
            page_number
            for page_number in job.requested_page_numbers_json
            if page_number not in persisted_page_numbers
        ]
        if not cancelled:
            failed_pages = list(dict.fromkeys([*failed_pages, *unpersisted_pages]))

        if terminal_failure:
            run_status = (
                OCRRunStatus.PARTIALLY_COMPLETED
                if processed_pages
                else OCRRunStatus.FAILED
            )
        elif cancelled and not processed_pages:
            run_status = OCRRunStatus.CANCELLED
        elif not processed_pages and not failed_pages:
            run_status = OCRRunStatus.FAILED
        elif failed_pages or cancelled:
            run_status = OCRRunStatus.PARTIALLY_COMPLETED
        else:
            run_status = OCRRunStatus.COMPLETED

        current_run_text = "\n".join(
            f"[PAGE {page.page_number}]\n{page.normalised_text}" for page in page_rows
        )
        run.status = run_status
        run.page_count_processed = len(processed_pages)
        run.page_count_failed = len(failed_pages)
        run.total_blocks = sum(page.block_count for page in page_rows)
        run.total_characters = sum(page.character_count for page in page_rows)
        run.average_confidence = (
            sum(confidence_rows) / len(confidence_rows) if confidence_rows else None
        )
        run.minimum_confidence = min(confidence_rows) if confidence_rows else None
        run.maximum_confidence = max(confidence_rows) if confidence_rows else None
        low_confidence_blocks = sum(
            confidence < self.low_confidence_threshold for confidence in confidence_rows
        )
        effective_page_numbers = list(processed_pages)
        effective_block_count = run.total_blocks
        effective_run_ids = [str(run.id)]
        if run_status in {
            OCRRunStatus.COMPLETED,
            OCRRunStatus.PARTIALLY_COMPLETED,
        }:
            effective_source = await OCRSourceChainService(self.session).resolve(run)
            run.content_hash = effective_source.content_hash
            effective_page_numbers = [
                page.page_number for page in effective_source.pages
            ]
            effective_block_count = effective_source.block_count
            effective_run_ids = [str(run_id) for run_id in effective_source.run_ids]
        else:
            run.content_hash = hashlib.sha256(
                current_run_text.encode("utf-8")
            ).hexdigest()
        run.warnings_json = list(
            dict.fromkeys(
                warning for page in page_rows for warning in page.warning_codes_json
            )
        )
        run.completed_at = completed_at
        run.metadata_json = {
            **(run.metadata_json or {}),
            "lowConfidenceBlocks": low_confidence_blocks,
            "lowConfidenceThreshold": self.low_confidence_threshold,
            "reviewConfidenceThreshold": self.review_confidence_threshold,
            "terminalFailure": terminal_failure,
            "unpersistedPageNumbers": unpersisted_pages,
            "effectivePageNumbers": effective_page_numbers,
            "effectiveBlockCount": effective_block_count,
            "effectiveOcrRunIds": effective_run_ids,
        }
        job.processed_page_numbers_json = processed_pages
        job.failed_page_numbers_json = failed_pages

        summary: dict[str, object] = {
            **dict(job.result_summary_json or {}),
            "runId": str(run.id),
            "provider": run.provider,
            "providerVersion": run.provider_version,
            "status": run_status.value,
            "pageCountRequested": run.page_count_requested,
            "pageCountProcessed": len(processed_pages),
            "pageCountFailed": len(failed_pages),
            "totalBlocks": run.total_blocks,
            "totalCharacters": run.total_characters,
            "averageConfidence": run.average_confidence,
            "minimumConfidence": run.minimum_confidence,
            "maximumConfidence": run.maximum_confidence,
            "lowConfidenceBlocks": low_confidence_blocks,
            "lowConfidenceThreshold": self.low_confidence_threshold,
            "reviewConfidenceThreshold": self.review_confidence_threshold,
            "terminalFailure": terminal_failure,
            "unpersistedPageNumbers": unpersisted_pages,
            "effectivePageNumbers": effective_page_numbers,
            "effectiveBlockCount": effective_block_count,
            "effectiveOcrRunIds": effective_run_ids,
            "warnings": list(run.warnings_json),
        }
        if terminal_failure:
            job.result_summary_json = summary
        elif cancelled:
            job.status = OCRJobStatus.CANCELLED
            job.progress = min(job.progress, 99)
            job.current_stage = "Cancelled"
            job.cancelled_at = completed_at
            job.result_summary_json = summary
        elif run_status is OCRRunStatus.COMPLETED:
            await self.jobs.mark_completed(
                job,
                status=OCRJobStatus.COMPLETED,
                completed_at=completed_at,
                summary=summary,
            )
        elif run_status is OCRRunStatus.PARTIALLY_COMPLETED:
            await self.jobs.mark_completed(
                job,
                status=OCRJobStatus.PARTIALLY_COMPLETED,
                completed_at=completed_at,
                summary=summary,
            )
        else:
            job.status = OCRJobStatus.FAILED
            job.progress = 100
            job.current_stage = "Failed"
            job.failed_at = completed_at
            job.error_code = "OCR_PAGE_FAILED"
            job.error_message = "All requested OCR pages failed."
            job.result_summary_json = summary

        if run_status in {
            OCRRunStatus.COMPLETED,
            OCRRunStatus.PARTIALLY_COMPLETED,
        }:
            latest_pointer_updated = await self.runs.set_latest_by_ids(
                document_file_id=job.document_file_id,
                ocr_run_id=run.id,
                source_extraction_run_id=run.source_extraction_run_id,
            )
            run.metadata_json = {
                **(run.metadata_json or {}),
                "latestPointerUpdated": latest_pointer_updated,
            }
        await self.session.flush()
        return run

    async def persisted_page_numbers(self, run_id: UUID) -> set[int]:
        rows = await self.session.scalars(
            select(OCRPageResult.page_number).where(OCRPageResult.ocr_run_id == run_id)
        )
        return {int(page) for page in rows}

    async def block_count(self, run_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(OCRBlock.id)).where(OCRBlock.ocr_run_id == run_id)
            )
            or 0
        )
