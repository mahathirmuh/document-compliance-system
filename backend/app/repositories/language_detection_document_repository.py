"""Scoped document-file inventory for the language-detection workspace."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.extracted_block import ExtractedBlock
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.language_detection_job import (
    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES,
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
)
from app.models.language_detection_run import LanguageDetectionRun
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import OCRJob, OCRJobStatus
from app.models.ocr_run import OCRRun, OCRRunStatus


@dataclass(frozen=True, slots=True)
class LanguageDetectionDocumentRow:
    """One current file plus its latest persisted pipeline state."""

    document_file: DocumentFile
    extraction_status: ExtractionJobStatus | None
    ocr_status: OCRJobStatus | None
    language_status: LanguageDetectionJobStatus | None
    language_progress: int | None
    language_current_stage: str | None
    language_active: bool
    native_block_count: int
    ocr_block_count: int


class LanguageDetectionDocumentRepository:
    """Read the Phase 7 language workspace without hiding undetected files."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        search: str | None,
        department_id: UUID | None,
        language_status: LanguageDetectionJobStatus | None,
        not_started: bool,
        scope_all_departments: bool,
        scope_department_id: UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[LanguageDetectionDocumentRow], int]:
        latest_extraction_status = (
            select(ExtractionJob.status)
            .where(ExtractionJob.document_file_id == DocumentFile.id)
            .order_by(
                ExtractionJob.requested_at.desc(),
                ExtractionJob.id.desc(),
            )
            .limit(1)
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        usable_ocr_pointer = (
            select(OCRRun.id)
            .where(
                OCRRun.id == DocumentFile.latest_ocr_run_id,
                OCRRun.document_file_id == DocumentFile.id,
                OCRRun.source_extraction_run_id
                == DocumentFile.latest_extraction_run_id,
                OCRRun.status.in_(
                    {
                        OCRRunStatus.COMPLETED,
                        OCRRunStatus.PARTIALLY_COMPLETED,
                    }
                ),
            )
            .correlate(DocumentFile)
            .exists()
        )
        ocr_run_is_latest = (
            select(OCRRun.id)
            .where(
                OCRRun.ocr_job_id == OCRJob.id,
                OCRRun.id == DocumentFile.latest_ocr_run_id,
                OCRRun.source_extraction_run_id
                == DocumentFile.latest_extraction_run_id,
            )
            .correlate(DocumentFile, OCRJob)
            .exists()
        )
        current_ocr_job_predicates = (
            OCRJob.document_file_id == DocumentFile.id,
            OCRJob.extraction_run_id == DocumentFile.latest_extraction_run_id,
            or_(
                OCRJob.status.not_in(
                    {
                        OCRJobStatus.COMPLETED,
                        OCRJobStatus.PARTIALLY_COMPLETED,
                    }
                ),
                ocr_run_is_latest,
            ),
        )
        latest_ocr_status = (
            select(OCRJob.status)
            .where(*current_ocr_job_predicates)
            .order_by(OCRJob.requested_at.desc(), OCRJob.id.desc())
            .limit(1)
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        current_language_source = (
            LanguageDetectionJob.document_file_id == DocumentFile.id,
            LanguageDetectionJob.extraction_run_id
            == DocumentFile.latest_extraction_run_id,
            or_(
                and_(
                    LanguageDetectionJob.ocr_run_id.is_(None),
                    ~usable_ocr_pointer,
                ),
                and_(
                    LanguageDetectionJob.ocr_run_id == DocumentFile.latest_ocr_run_id,
                    usable_ocr_pointer,
                ),
            ),
        )
        language_run_is_latest = (
            select(LanguageDetectionRun.id)
            .where(
                LanguageDetectionRun.job_id == LanguageDetectionJob.id,
                LanguageDetectionRun.id
                == DocumentFile.latest_language_detection_run_id,
                LanguageDetectionRun.extraction_run_id
                == DocumentFile.latest_extraction_run_id,
            )
            .correlate(DocumentFile, LanguageDetectionJob)
            .exists()
        )
        current_language_job_predicates = (
            *current_language_source,
            or_(
                LanguageDetectionJob.status.not_in(
                    {
                        LanguageDetectionJobStatus.COMPLETED,
                        LanguageDetectionJobStatus.PARTIALLY_COMPLETED,
                    }
                ),
                language_run_is_latest,
            ),
        )
        latest_language_status = (
            select(LanguageDetectionJob.status)
            .where(*current_language_job_predicates)
            .order_by(
                LanguageDetectionJob.requested_at.desc(),
                LanguageDetectionJob.id.desc(),
            )
            .limit(1)
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        latest_language_progress = (
            select(LanguageDetectionJob.progress)
            .where(*current_language_job_predicates)
            .order_by(
                LanguageDetectionJob.requested_at.desc(),
                LanguageDetectionJob.id.desc(),
            )
            .limit(1)
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        latest_language_current_stage = (
            select(LanguageDetectionJob.current_stage)
            .where(*current_language_job_predicates)
            .order_by(
                LanguageDetectionJob.requested_at.desc(),
                LanguageDetectionJob.id.desc(),
            )
            .limit(1)
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        language_active = (
            select(func.count(LanguageDetectionJob.id))
            .where(
                *current_language_source,
                LanguageDetectionJob.status.in_(ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES),
            )
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        native_block_count = (
            select(func.count(ExtractedBlock.id))
            .where(
                ExtractedBlock.extraction_run_id
                == DocumentFile.latest_extraction_run_id
            )
            .correlate(DocumentFile)
            .scalar_subquery()
        )
        ocr_block_count = (
            select(func.count(OCRBlock.id))
            .where(OCRBlock.ocr_run_id == DocumentFile.latest_ocr_run_id)
            .correlate(DocumentFile)
            .scalar_subquery()
        )

        predicates: list[object] = [
            DocumentFile.file_status == DocumentFileStatus.AVAILABLE,
            DocumentFile.is_current.is_(True),
            DocumentFile.deleted_at.is_(None),
            Document.deleted_at.is_(None),
            Document.is_archived.is_(False),
            DocumentRevision.deleted_at.is_(None),
            DocumentRevision.is_current.is_(True),
        ]
        if department_id is not None:
            predicates.append(Document.department_id == department_id)
        if not scope_all_departments:
            predicates.append(
                Document.department_id == scope_department_id
                if scope_department_id is not None
                else false()
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    Document.base_document_code.ilike(pattern),
                    Document.title.ilike(pattern),
                    DocumentRevision.full_document_code.ilike(pattern),
                    DocumentFile.original_filename.ilike(pattern),
                )
            )
        if not_started:
            predicates.append(latest_language_status.is_(None))
        elif language_status is not None:
            predicates.append(latest_language_status == language_status)

        base = (
            select(DocumentFile.id)
            .join(Document, Document.id == DocumentFile.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id == DocumentFile.document_revision_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )

        sort_columns = {
            "documentCode": Document.base_document_code,
            "filename": DocumentFile.original_filename,
            "uploadedAt": DocumentFile.uploaded_at,
        }
        sort_column = sort_columns.get(
            sort_by,
            Document.base_document_code,
        )
        ascending = sort_order.lower() == "asc"
        ordering = sort_column.asc() if ascending else sort_column.desc()
        tie_breaker = DocumentFile.id.asc() if ascending else DocumentFile.id.desc()
        statement = (
            select(
                DocumentFile,
                latest_extraction_status.label("extraction_status"),
                latest_ocr_status.label("ocr_status"),
                latest_language_status.label("language_status"),
                latest_language_progress.label("language_progress"),
                latest_language_current_stage.label("language_current_stage"),
                language_active.label("language_active"),
                native_block_count.label("native_block_count"),
                ocr_block_count.label("ocr_block_count"),
            )
            .join(Document, Document.id == DocumentFile.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id == DocumentFile.document_revision_id,
            )
            .where(*predicates)
            .options(
                joinedload(DocumentFile.document),
                joinedload(DocumentFile.revision),
                joinedload(DocumentFile.latest_extraction_run),
                joinedload(DocumentFile.latest_ocr_run),
                joinedload(DocumentFile.latest_language_detection_run),
            )
            .order_by(ordering, tie_breaker)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(statement)).unique().all()
        return [
            LanguageDetectionDocumentRow(
                document_file=row[0],
                extraction_status=row[1],
                ocr_status=row[2],
                language_status=row[3],
                language_progress=row[4],
                language_current_stage=row[5],
                language_active=bool(row[6]),
                native_block_count=int(row[7] or 0),
                ocr_block_count=int(row[8] or 0),
            )
            for row in rows
        ], total
