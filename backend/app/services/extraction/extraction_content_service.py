"""Read-only extracted-content queries with department scoping."""

from __future__ import annotations

from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, has_permission
from app.core.config import Settings
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extracted_table_cell import ExtractedTableCell
from app.models.extraction_run import ExtractionRun, ExtractorType
from app.models.language_block_result import (
    LanguageBlockResult,
    LanguageCode,
)
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.ocr_block import OCRBlock
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.extracted_block_repository import ExtractedBlockRepository
from app.repositories.extracted_container_repository import (
    ExtractedContainerRepository,
)
from app.repositories.extracted_table_repository import (
    ExtractedTableRepository,
)
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_run_repository import OCRRunRepository
from app.schemas.common import PaginationData
from app.schemas.extracted_content import (
    ExtractedBlockResponse,
    ExtractedContainerExportResponse,
    ExtractedContainerResponse,
    ExtractedContentSearchItem,
    ExtractedContentSearchResponse,
    ExtractedContentSource,
    ExtractedTableCellResponse,
    ExtractedTableExportResponse,
    ExtractedTableResponse,
)
from app.schemas.extraction_job import (
    ExtractionDocumentReference,
    ExtractionFileReference,
    ExtractionRequesterReference,
    ExtractionRevisionReference,
)
from app.schemas.extraction_run import (
    ExtractionRunHistoryItem,
    ExtractionRunResponse,
    ExtractionRunSummary,
)
from app.schemas.ocr_internal import OCRMergedBlock
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import (
    DocumentServiceBase,
    document_error,
)
from app.services.ocr.ocr_merge_service import OCRMergeService
from app.services.ocr.ocr_source_chain_service import (
    OCRSourceChainError,
    OCRSourceChainService,
)


def extraction_run_not_found() -> Exception:
    return document_error(
        "The extraction result does not exist or is outside your access scope.",
        status_code=HTTPStatus.NOT_FOUND,
        title="Extraction result was not found.",
    )


class ExtractionContentService(DocumentServiceBase):
    """Retrieve durable extraction results without exposing storage details."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.runs = ExtractionRunRepository(session)
        self.files = DocumentFileRepository(session)
        self.containers = ExtractedContainerRepository(session)
        self.blocks = ExtractedBlockRepository(session)
        self.tables = ExtractedTableRepository(session)
        self.ocr_runs = OCRRunRepository(session)
        self.ocr_blocks = OCRBlockRepository(session)
        self.language_runs = LanguageDetectionRunRepository(session)
        self.language_blocks = LanguageBlockResultRepository(session)
        self.ocr_merge = OCRMergeService()

    async def latest_for_file(
        self,
        document_file_id: UUID,
    ) -> ExtractionRunResponse:
        document_file = await self.files.get_by_id(document_file_id)
        if document_file is None:
            raise extraction_run_not_found()
        self._ensure_document_access(document_file.document)
        run = await self.runs.get_latest_by_file(document_file_id)
        if run is None:
            raise extraction_run_not_found()
        self._ensure_run_visibility(run)
        return extraction_run_response(run)

    async def history_for_file(
        self,
        document_file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> PaginationData[ExtractionRunHistoryItem]:
        document_file = await self.files.get_by_id(document_file_id)
        if document_file is None:
            raise extraction_run_not_found()
        self._ensure_document_access(document_file.document)
        total = await self.runs.count_by_file(document_file_id)
        runs = await self.runs.list_by_file(
            document_file_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return PaginationData(
            items=[extraction_history_item(run) for run in runs],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def get_run(self, run_id: UUID) -> ExtractionRunResponse:
        run = await self._run(run_id)
        return extraction_run_response(run)

    async def list_containers(
        self,
        run_id: UUID,
        *,
        container_type: ExtractedContainerType | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> PaginationData[ExtractedContainerResponse]:
        await self._run(run_id)
        items, total = await self.containers.list(
            run_id,
            container_type=container_type,
            search=search,
            page=page,
            page_size=page_size,
        )
        return PaginationData(
            items=[container_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_blocks(
        self,
        run_id: UUID,
        *,
        container_id: UUID | None,
        block_type: ExtractedBlockType | None,
        content_source: ExtractedContentSource | None,
        language_code: LanguageCode | None,
        search: str | None,
        page: int,
        page_size: int,
        sort_order: str,
    ) -> PaginationData[ExtractedBlockResponse]:
        run = await self._run(run_id)
        ocr_run = await self._viewer_ocr_run(run)
        language_run = await self._viewer_language_run(run)
        if ocr_run is not None:
            return await self._list_merged_blocks(
                run,
                ocr_run=ocr_run,
                language_run=language_run,
                container_id=container_id,
                block_type=block_type,
                content_source=content_source,
                language_code=language_code,
                search=search,
                page=page,
                page_size=page_size,
                sort_order=sort_order,
            )
        if content_source == "OCR":
            return PaginationData(
                items=[],
                page=page,
                pageSize=page_size,
                totalItems=0,
                totalPages=0,
            )
        annotations: tuple[
            dict[UUID, LanguageBlockResult],
            dict[UUID, LanguageBlockResult],
        ] = ({}, {})
        matching_block_ids: list[UUID] | None = None
        if language_code is not None:
            annotations = await self._source_annotations(
                language_run,
                native_ids=None,
                ocr_ids=None,
                language_code=language_code,
            )
            matching_block_ids = list(annotations[0])
        items, total = await self.blocks.list(
            run_id,
            container_id=container_id,
            block_type=block_type,
            block_ids=matching_block_ids,
            search=search,
            page=page,
            page_size=page_size,
            sort_order=sort_order,
        )
        if language_code is None:
            annotations = await self._source_annotations(
                language_run,
                native_ids=[item.id for item in items],
                ocr_ids=[],
            )
        return PaginationData(
            items=[
                block_response(
                    item,
                    language_result=annotations[0].get(item.id),
                )
                for item in items
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_tables(
        self,
        run_id: UUID,
        *,
        container_id: UUID | None,
        search: str | None,
        include_cells: bool,
        page: int,
        page_size: int,
    ) -> PaginationData[ExtractedTableResponse]:
        await self._run(run_id)
        items, total = await self.tables.list(
            run_id,
            container_id=container_id,
            search=search,
            include_cells=False,
            page=page,
            page_size=page_size,
        )
        responses: list[ExtractedTableResponse] = []
        for item in items:
            cells: list[ExtractedTableCell] = []
            cell_total = 0
            if include_cells:
                cells, cell_total = await self.tables.list_cells(
                    item.id,
                    page=1,
                    page_size=500,
                )
            responses.append(
                table_response(
                    item,
                    include_cells=include_cells,
                    cells=cells,
                    total_cells=cell_total,
                )
            )
        return PaginationData(
            items=responses,
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def _list_merged_blocks(
        self,
        run: ExtractionRun,
        *,
        ocr_run: OCRRun | None,
        language_run: LanguageDetectionRun | None,
        container_id: UUID | None,
        block_type: ExtractedBlockType | None,
        content_source: ExtractedContentSource | None,
        language_code: LanguageCode | None,
        search: str | None,
        page: int,
        page_size: int,
        sort_order: str,
    ) -> PaginationData[ExtractedBlockResponse]:
        native_blocks, native_total = await self.blocks.list(
            run.id,
            page=1,
            page_size=max(1, int(run.total_blocks)),
            sort_order="asc",
        )
        if len(native_blocks) < native_total:
            native_blocks, _ = await self.blocks.list(
                run.id,
                page=1,
                page_size=native_total,
                sort_order="asc",
            )

        container_limit = max(
            1,
            int(run.total_pages),
            int(run.total_sheets),
        )
        containers, container_total = await self.containers.list(
            run.id,
            page=1,
            page_size=container_limit,
        )
        if len(containers) < container_total:
            containers, _ = await self.containers.list(
                run.id,
                page=1,
                page_size=container_total,
            )
        page_containers = {
            item.container_index: item
            for item in containers
            if item.container_type is ExtractedContainerType.PDF_PAGE
        }

        ocr_rows: list[tuple[OCRBlock, int]] = []
        if ocr_run is not None:
            try:
                effective_source = await OCRSourceChainService(self.session).resolve(
                    ocr_run
                )
            except OCRSourceChainError as exc:
                raise document_error(
                    "The effective OCR result could not be resolved.",
                    title="OCR result is not available.",
                ) from exc
            for source_group in effective_source.pages_by_run:
                block_limit = sum(page.block_count for page in source_group.pages)
                if block_limit == 0:
                    continue
                source_rows, source_total = await self.ocr_blocks.list_by_run(
                    source_group.run_id,
                    page_numbers=source_group.page_numbers,
                    limit=max(1, block_limit),
                )
                if len(source_rows) < source_total:
                    source_rows, _ = await self.ocr_blocks.list_by_run(
                        source_group.run_id,
                        page_numbers=source_group.page_numbers,
                        limit=source_total,
                    )
                ocr_rows.extend(source_rows)

        native_by_id = {item.id: item for item in native_blocks}
        ocr_by_id = {item.id: (item, page_number) for item, page_number in ocr_rows}
        merged = self.ocr_merge.merge_native_and_ocr(
            [
                {
                    "id": item.id,
                    "extraction_run_id": item.extraction_run_id,
                    "container_id": item.container_id,
                    "page_number": item.container.container_index,
                    "block_order": item.block_order,
                    "source_reference": item.source_reference,
                    "text": item.text,
                    "normalised_text": item.normalised_text,
                }
                for item in native_blocks
            ],
            [
                {
                    "id": item.id,
                    "ocr_run_id": item.ocr_run_id,
                    "ocr_page_result_id": item.ocr_page_result_id,
                    "page_number": page_number,
                    "block_order": item.block_order,
                    "text": item.text,
                    "normalised_text": item.normalised_text,
                    "confidence": item.confidence,
                    "provider_model": item.provider_model,
                    "recognition_profile": item.recognition_profile,
                }
                for item, page_number in ocr_rows
            ],
            selectable_text_minimum=int(
                self.settings.ocr_selectable_text_min_characters
            ),
        )

        normalized_search = (search or "").strip().casefold()
        candidates: list[tuple[OCRMergedBlock, ExtractedContainer]] = []
        for item in merged:
            source_id = UUID(item.source_id)
            if item.source == "NATIVE":
                native = native_by_id[source_id]
                candidate_container = native.container
                item_block_type = native.block_type
                source_reference = native.source_reference
            else:
                ocr, page_number = ocr_by_id[source_id]
                page_container = page_containers.get(page_number)
                if page_container is None:
                    continue
                candidate_container = page_container
                item_block_type = ExtractedBlockType.TEXT
                source_reference = _ocr_source_reference(
                    page_number,
                    ocr.block_order,
                )
            if (
                container_id is not None
                and candidate_container.id != container_id
            ):
                continue
            if block_type is not None and item_block_type is not block_type:
                continue
            if content_source is not None and item.source != content_source:
                continue
            if normalized_search and not any(
                normalized_search in value.casefold()
                for value in (
                    item.text,
                    item.normalised_text,
                    source_reference,
                )
            ):
                continue
            candidates.append((item, candidate_container))

        annotations: tuple[
            dict[UUID, LanguageBlockResult],
            dict[UUID, LanguageBlockResult],
        ] = ({}, {})
        if language_code is not None:
            annotations = await self._source_annotations(
                language_run,
                native_ids=None,
                ocr_ids=None,
                language_code=language_code,
            )
            candidates = [
                candidate
                for candidate in candidates
                if _language_result_for(candidate[0], annotations) is not None
            ]

        if sort_order.lower() == "desc":
            candidates.reverse()
        total = len(candidates)
        offset = (page - 1) * page_size
        page_candidates = candidates[offset : offset + page_size]
        if language_code is None:
            annotations = await self._source_annotations(
                language_run,
                native_ids=[
                    UUID(item.source_id)
                    for item, _ in page_candidates
                    if item.source == "NATIVE"
                ],
                ocr_ids=[
                    UUID(item.source_id)
                    for item, _ in page_candidates
                    if item.source == "OCR"
                ],
            )

        responses: list[ExtractedBlockResponse] = []
        for item, container in page_candidates:
            source_id = UUID(item.source_id)
            language_result = _language_result_for(item, annotations)
            if item.source == "NATIVE":
                responses.append(
                    block_response(
                        native_by_id[source_id],
                        language_result=language_result,
                        provenance=item.provenance,
                    )
                )
                continue
            ocr, page_number = ocr_by_id[source_id]
            responses.append(
                ocr_content_block_response(
                    ocr,
                    page_number=page_number,
                    extraction_run_id=run.id,
                    container=container,
                    language_result=language_result,
                    provenance=item.provenance,
                )
            )
        return PaginationData(
            items=responses,
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def _viewer_ocr_run(
        self,
        run: ExtractionRun,
    ) -> OCRRun | None:
        if run.extractor_type is not ExtractorType.PDF or not has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_OCR_RESULTS,
            is_superuser=self.user.is_superuser,
        ):
            return None
        latest_id = run.document_file.latest_ocr_run_id
        if latest_id is None:
            return None
        ocr_run = await self.ocr_runs.get_by_id(latest_id)
        if (
            ocr_run is None
            or ocr_run.source_extraction_run_id != run.id
            or ocr_run.status
            not in {
                OCRRunStatus.COMPLETED,
                OCRRunStatus.PARTIALLY_COMPLETED,
            }
        ):
            return None
        return ocr_run

    async def _viewer_language_run(
        self,
        run: ExtractionRun,
    ) -> LanguageDetectionRun | None:
        if not has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
            is_superuser=self.user.is_superuser,
        ):
            return None
        latest_id = run.document_file.latest_language_detection_run_id
        if latest_id is None:
            return None
        language_run = await self.language_runs.get_by_id(latest_id)
        if (
            language_run is None
            or language_run.extraction_run_id != run.id
            or language_run.status
            not in {
                LanguageDetectionRunStatus.COMPLETED,
                LanguageDetectionRunStatus.PARTIALLY_COMPLETED,
            }
        ):
            return None
        return language_run

    async def _source_annotations(
        self,
        run: LanguageDetectionRun | None,
        *,
        native_ids: list[UUID] | None,
        ocr_ids: list[UUID] | None,
        language_code: LanguageCode | None = None,
    ) -> tuple[
        dict[UUID, LanguageBlockResult],
        dict[UUID, LanguageBlockResult],
    ]:
        if run is None:
            return {}, {}
        results = await self.language_blocks.list_source_annotations(
            run.id,
            extracted_block_ids=native_ids,
            ocr_block_ids=ocr_ids,
            language_code=language_code,
        )
        native: dict[UUID, LanguageBlockResult] = {}
        ocr: dict[UUID, LanguageBlockResult] = {}
        for result in results:
            if result.extracted_block_id is not None:
                native[result.extracted_block_id] = result
            elif result.ocr_block_id is not None:
                ocr[result.ocr_block_id] = result
        return native, ocr

    async def search(
        self,
        run_id: UUID,
        *,
        query: str,
    ) -> ExtractedContentSearchResponse:
        await self._run(run_id)
        normalized_query = query.strip()
        if not normalized_query:
            raise document_error(
                "A non-empty search query is required.",
                field="q",
                title="Extracted-content search is invalid.",
            )
        items, total = await self.blocks.search(
            run_id,
            normalized_query,
            limit=self.settings.extraction_search_max_results,
        )
        return ExtractedContentSearchResponse(
            query=normalized_query,
            total_matches=total,
            items=[
                ExtractedContentSearchItem(
                    block_id=item.id,
                    block_order=item.block_order,
                    container_id=item.container_id,
                    container_index=item.container.container_index,
                    container_name=item.container.name,
                    source_reference=item.source_reference,
                    block_type=item.block_type,
                    snippet=_plain_text_snippet(
                        item.normalised_text,
                        normalized_query,
                    ),
                    location=item.location_json,
                )
                for item in items
            ],
        )

    async def _run(self, run_id: UUID) -> ExtractionRun:
        run = await self.runs.get_by_id(run_id)
        if run is None:
            raise extraction_run_not_found()
        self._ensure_run_visibility(run)
        return run

    def _ensure_run_visibility(self, run: ExtractionRun) -> None:
        self._ensure_document_access(run.document)
        if self._can_view_extraction_history:
            return
        if not _is_current_available_file_run(run.document_file, run.id):
            raise extraction_run_not_found()

    @property
    def _can_view_extraction_history(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
            is_superuser=self.user.is_superuser,
        )

    def _ensure_document_access(self, document: object) -> None:
        try:
            self.policy.ensure_document_access(document)  # type: ignore[arg-type]
        except Exception as exc:
            raise extraction_run_not_found() from exc


def _warning_texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    warnings: list[str] = []
    for item in value:
        if isinstance(item, str):
            warnings.append(item)
        elif isinstance(item, dict):
            message = item.get("message")
            if isinstance(message, str):
                warnings.append(message)
    return warnings


def extraction_run_summary(run: ExtractionRun) -> ExtractionRunSummary:
    return ExtractionRunSummary(
        run_id=run.id,
        status=run.status,
        extractor_type=run.extractor_type,
        total_pages=run.total_pages,
        total_sheets=run.total_sheets,
        total_blocks=run.total_blocks,
        total_paragraphs=run.total_paragraphs,
        total_tables=run.total_tables,
        total_cells=run.total_cells,
        total_characters=run.total_characters,
        total_words=run.total_words,
        has_selectable_text=run.has_selectable_text,
        requires_ocr=run.requires_ocr,
        warnings=_warning_texts(run.warnings_json),
    )


def extraction_run_response(run: ExtractionRun) -> ExtractionRunResponse:
    summary = extraction_run_summary(run)
    return ExtractionRunResponse(
        **summary.model_dump(),
        extraction_job_id=run.extraction_job_id,
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
        extractor_version=run.extractor_version,
        source_sha256_hash=run.source_sha256_hash,
        source_file_size=run.source_file_size,
        content_hash=run.content_hash,
        metadata=run.metadata_json,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        is_latest=run.document_file.latest_extraction_run_id == run.id,
    )


def extraction_history_item(run: ExtractionRun) -> ExtractionRunHistoryItem:
    warnings = _warning_texts(run.warnings_json)
    metadata = run.metadata_json or {}
    reason = metadata.get("reExtractionReason")
    return ExtractionRunHistoryItem(
        id=run.id,
        extraction_job_id=run.extraction_job_id,
        extractor_type=run.extractor_type,
        extractor_version=run.extractor_version,
        status=run.status,
        source_sha256_hash=run.source_sha256_hash,
        content_hash=run.content_hash,
        summary=extraction_run_summary(run),
        requested_by=(
            ExtractionRequesterReference(
                id=run.extraction_job.requester.id,
                name=run.extraction_job.requester.name,
            )
            if run.extraction_job.requester is not None
            else None
        ),
        re_extraction_reason=reason if isinstance(reason, str) else None,
        warnings=warnings,
        completed_at=run.completed_at,
        is_latest=run.document_file.latest_extraction_run_id == run.id,
    )


def container_response(
    container: ExtractedContainer,
) -> ExtractedContainerResponse:
    return ExtractedContainerResponse(
        id=container.id,
        extraction_run_id=container.extraction_run_id,
        container_type=container.container_type,
        container_index=container.container_index,
        name=container.name,
        title=container.title,
        character_count=container.character_count,
        word_count=container.word_count,
        metadata=container.metadata_json,
        created_at=container.created_at,
    )


def container_export_response(
    container: ExtractedContainer,
) -> ExtractedContainerExportResponse:
    """Serialize full container text only for an authorized export."""
    return ExtractedContainerExportResponse(
        **container_response(container).model_dump(),
        raw_text=container.raw_text,
        normalised_text=container.normalised_text,
    )


def block_response(
    block: ExtractedBlock,
    *,
    language_result: LanguageBlockResult | None = None,
    provenance: dict[str, object] | None = None,
) -> ExtractedBlockResponse:
    source_provenance = provenance or {
        "source": "EXTRACTION",
        "extractionRunId": str(block.extraction_run_id),
        "extractedBlockId": str(block.id),
        "containerId": str(block.container_id),
        "sourceReference": block.source_reference,
    }
    return ExtractedBlockResponse(
        id=block.id,
        extraction_run_id=block.extraction_run_id,
        container_id=block.container_id,
        parent_block_id=block.parent_block_id,
        block_type=block.block_type,
        block_order=block.block_order,
        source_reference=block.source_reference,
        text=block.text,
        normalised_text=block.normalised_text,
        style_name=block.style_name,
        heading_level=block.heading_level,
        location=block.location_json,
        metadata=block.metadata_json,
        character_count=block.character_count,
        word_count=block.word_count,
        created_at=block.created_at,
        content_source="NATIVE",
        language_code=(
            language_result.language_code if language_result is not None else None
        ),
        language_confidence=(
            float(language_result.confidence) if language_result is not None else None
        ),
        ocr_confidence=None,
        provenance=_language_provenance(
            source_provenance,
            language_result,
        ),
    )


def ocr_content_block_response(
    block: OCRBlock,
    *,
    page_number: int,
    extraction_run_id: UUID,
    container: ExtractedContainer,
    language_result: LanguageBlockResult | None,
    provenance: dict[str, object],
) -> ExtractedBlockResponse:
    """Serialize an OCR block into the Phase 6-compatible viewer shape."""
    metadata = dict(block.metadata_json or {})
    metadata.update(
        {
            "providerModel": block.provider_model,
            "recognitionProfile": block.recognition_profile,
        }
    )
    return ExtractedBlockResponse(
        id=block.id,
        extraction_run_id=extraction_run_id,
        container_id=container.id,
        parent_block_id=None,
        block_type=ExtractedBlockType.TEXT,
        block_order=block.block_order,
        source_reference=(
            language_result.source_reference
            if language_result is not None
            else _ocr_source_reference(page_number, block.block_order)
        ),
        text=block.text,
        normalised_text=block.normalised_text,
        style_name=None,
        heading_level=None,
        location={
            "pageNumber": page_number,
            "bbox": block.bbox_json,
            "polygon": block.polygon_json,
            "orientation": block.orientation,
        },
        metadata=metadata,
        character_count=block.character_count,
        word_count=len(block.normalised_text.split()),
        created_at=block.created_at,
        content_source="OCR",
        language_code=(
            language_result.language_code if language_result is not None else None
        ),
        language_confidence=(
            float(language_result.confidence) if language_result is not None else None
        ),
        ocr_confidence=float(block.confidence),
        provenance=_language_provenance(provenance, language_result),
    )


def _language_result_for(
    block: OCRMergedBlock,
    annotations: tuple[
        dict[UUID, LanguageBlockResult],
        dict[UUID, LanguageBlockResult],
    ],
) -> LanguageBlockResult | None:
    source_id = UUID(block.source_id)
    return (
        annotations[0].get(source_id)
        if block.source == "NATIVE"
        else annotations[1].get(source_id)
    )


def _language_provenance(
    source_provenance: dict[str, object],
    result: LanguageBlockResult | None,
) -> dict[str, object]:
    provenance = {
        key: value for key, value in source_provenance.items() if value is not None
    }
    if result is not None:
        provenance.update(
            {
                "languageDetectionRunId": str(result.language_detection_run_id),
                "languageBlockResultId": str(result.id),
            }
        )
    return provenance


def _ocr_source_reference(page_number: int, block_order: int) -> str:
    return f"OCR:page={page_number}:block={block_order}"


def cell_response(cell: ExtractedTableCell) -> ExtractedTableCellResponse:
    return ExtractedTableCellResponse(
        id=cell.id,
        extracted_table_id=cell.extracted_table_id,
        row_index=cell.row_index,
        column_index=cell.column_index,
        row_span=cell.row_span,
        column_span=cell.column_span,
        coordinate=cell.coordinate,
        text=cell.text,
        normalised_text=cell.normalised_text,
        metadata=cell.metadata_json,
        created_at=cell.created_at,
    )


def table_response(
    table: ExtractedTable,
    *,
    include_cells: bool,
    cells: list[ExtractedTableCell] | None = None,
    total_cells: int | None = None,
) -> ExtractedTableResponse:
    serialized_cells = (
        (cells if cells is not None else list(table.cells)) if include_cells else []
    )
    metadata = dict(table.metadata_json or {})
    if include_cells and total_cells is not None:
        metadata["totalCells"] = total_cells
        metadata["cellsTruncated"] = total_cells > len(serialized_cells)
    return ExtractedTableResponse(
        id=table.id,
        extraction_run_id=table.extraction_run_id,
        container_id=table.container_id,
        source_reference=table.source_reference,
        table_index=table.table_index,
        row_count=table.row_count,
        column_count=table.column_count,
        metadata=metadata,
        cells=[cell_response(cell) for cell in serialized_cells],
        created_at=table.created_at,
    )


def table_export_response(
    table: ExtractedTable,
    *,
    include_cells: bool,
    cells: list[ExtractedTableCell] | None = None,
    total_cells: int | None = None,
) -> ExtractedTableExportResponse:
    """Serialize full table text only for an authorized export."""
    return ExtractedTableExportResponse(
        **table_response(
            table,
            include_cells=include_cells,
            cells=cells,
            total_cells=total_cells,
        ).model_dump(),
        raw_text=table.raw_text,
    )


def _plain_text_snippet(
    text: str,
    query: str,
    *,
    radius: int = 100,
) -> str:
    """Return escaped-by-construction plain text; the frontend highlights it."""
    if not text:
        return ""
    index = text.casefold().find(query.casefold())
    if index < 0:
        return text[: 2 * radius]
    start = max(0, index - radius)
    end = min(len(text), index + len(query) + radius)
    prefix = "\N{HORIZONTAL ELLIPSIS}" if start else ""
    suffix = "\N{HORIZONTAL ELLIPSIS}" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _is_current_available_file_run(
    document_file: DocumentFile,
    run_id: UUID,
) -> bool:
    return (
        document_file.file_status == DocumentFileStatus.AVAILABLE
        and document_file.is_current
        and document_file.deleted_at is None
        and document_file.latest_extraction_run_id == run_id
    )
