"""Language block persistence, merged-source loading, and filtered reads."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extracted_block import ExtractedBlock
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.language_block_result import (
    LanguageBlockResult,
    LanguageCode,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.models.ocr_block import OCRBlock
from app.models.ocr_page_result import OCRPageResult
from app.schemas.language_internal import LanguageSourceBlockData


@dataclass(frozen=True, slots=True)
class LanguageBlockReadRow:
    result: LanguageBlockResult
    text: str
    source_confidence: float | None


class LanguageBlockResultRepository:
    """Keep SQL joins and pagination out of business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(
        self,
        results: Sequence[LanguageBlockResult],
    ) -> list[LanguageBlockResult]:
        if not results:
            return []
        self.session.add_all(results)
        await self.session.flush()
        return list(results)

    async def load_native_sources(
        self,
        extraction_run_id: UUID,
        *,
        limit: int,
    ) -> list[LanguageSourceBlockData]:
        statement = (
            select(ExtractedBlock, ExtractedContainer)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedBlock.container_id,
            )
            .where(ExtractedBlock.extraction_run_id == extraction_run_id)
            .order_by(
                ExtractedContainer.container_index,
                ExtractedBlock.block_order,
                ExtractedBlock.id,
            )
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            LanguageSourceBlockData(
                source_type=LanguageSourceType.NATIVE_EXTRACTION,
                extracted_block_id=block.id,
                ocr_block_id=None,
                container_id=container.id,
                container_type=container.container_type.value,
                container_name=container.name or container.title,
                container_index=container.container_index,
                page_number=(
                    container.container_index
                    if container.container_type
                    is ExtractedContainerType.PDF_PAGE
                    else None
                ),
                block_order=block.block_order,
                source_reference=block.source_reference,
                text=block.text,
                normalised_text=block.normalised_text,
                source_confidence=None,
                source_metadata=dict(block.metadata_json or {}),
            )
            for block, container in rows
        ]

    async def load_ocr_sources(
        self,
        ocr_run_id: UUID,
        *,
        extraction_run_id: UUID,
        limit: int,
    ) -> list[LanguageSourceBlockData]:
        statement = (
            select(OCRBlock, OCRPageResult, ExtractedContainer)
            .join(
                OCRPageResult,
                OCRPageResult.id == OCRBlock.ocr_page_result_id,
            )
            .outerjoin(
                ExtractedContainer,
                (
                    ExtractedContainer.extraction_run_id
                    == extraction_run_id
                )
                & (
                    ExtractedContainer.container_type
                    == ExtractedContainerType.PDF_PAGE
                )
                & (
                    ExtractedContainer.container_index
                    == OCRPageResult.page_number
                ),
            )
            .where(OCRBlock.ocr_run_id == ocr_run_id)
            .order_by(
                OCRPageResult.page_number,
                OCRBlock.block_order,
                OCRBlock.id,
            )
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            LanguageSourceBlockData(
                source_type=LanguageSourceType.OCR,
                extracted_block_id=None,
                ocr_block_id=block.id,
                container_id=container.id if container is not None else None,
                container_type=ExtractedContainerType.PDF_PAGE.value,
                container_name=(
                    container.name
                    if container is not None
                    else f"Page {page.page_number}"
                ),
                container_index=page.page_number,
                page_number=page.page_number,
                block_order=block.block_order,
                source_reference=(
                    f"OCR:page={page.page_number}:block={block.block_order}"
                ),
                text=block.text,
                normalised_text=block.normalised_text,
                source_confidence=block.confidence,
                source_metadata={
                    **dict(block.metadata_json or {}),
                    "ocrPageResultId": str(page.id),
                    "providerModel": block.provider_model,
                    "recognitionProfile": block.recognition_profile,
                    "bbox": block.bbox_json,
                    "polygon": block.polygon_json,
                },
            )
            for block, page, container in rows
        ]

    async def list(
        self,
        language_detection_run_id: UUID,
        *,
        language_code: LanguageCode | None = None,
        source_type: LanguageSourceType | None = None,
        container_id: UUID | None = None,
        minimum_confidence: float | None = None,
        maximum_confidence: float | None = None,
        is_mixed: bool | None = None,
        eligibility_status: LanguageEligibilityStatus | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[LanguageBlockReadRow], int]:
        predicates: list[object] = [
            LanguageBlockResult.language_detection_run_id
            == language_detection_run_id
        ]
        if language_code is not None:
            predicates.append(
                LanguageBlockResult.language_code == language_code
            )
        if source_type is not None:
            predicates.append(
                LanguageBlockResult.source_type == source_type
            )
        if container_id is not None:
            predicates.append(
                LanguageBlockResult.container_id == container_id
            )
        if minimum_confidence is not None:
            predicates.append(
                LanguageBlockResult.confidence >= minimum_confidence
            )
        if maximum_confidence is not None:
            predicates.append(
                LanguageBlockResult.confidence <= maximum_confidence
            )
        if is_mixed is not None:
            predicates.append(LanguageBlockResult.is_mixed == is_mixed)
        if eligibility_status is not None:
            predicates.append(
                LanguageBlockResult.eligibility_status
                == eligibility_status
            )
        source_text = func.coalesce(ExtractedBlock.text, OCRBlock.text, "")
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    source_text.ilike(pattern),
                    LanguageBlockResult.source_reference.ilike(pattern),
                )
            )
        source_confidence = OCRBlock.confidence
        base = (
            select(
                LanguageBlockResult,
                source_text.label("source_text"),
                source_confidence.label("source_confidence"),
            )
            .outerjoin(
                ExtractedBlock,
                ExtractedBlock.id
                == LanguageBlockResult.extracted_block_id,
            )
            .outerjoin(
                OCRBlock,
                OCRBlock.id == LanguageBlockResult.ocr_block_id,
            )
            .outerjoin(
                ExtractedContainer,
                ExtractedContainer.id
                == LanguageBlockResult.container_id,
            )
            .where(*predicates)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        source_order = func.coalesce(
            ExtractedBlock.block_order,
            OCRBlock.block_order,
            0,
        )
        statement = (
            base.order_by(
                func.coalesce(ExtractedContainer.container_index, 0),
                source_order,
                LanguageBlockResult.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            LanguageBlockReadRow(
                result=row[0],
                text=str(row[1] or ""),
                source_confidence=(
                    float(row[2]) if row[2] is not None else None
                ),
            )
            for row in rows
        ], total

    async def list_for_export(
        self,
        language_detection_run_id: UUID,
        *,
        limit: int,
    ) -> list[LanguageBlockReadRow]:
        rows, _ = await self.list(
            language_detection_run_id,
            page=1,
            page_size=limit,
        )
        return rows

    async def list_source_annotations(
        self,
        language_detection_run_id: UUID,
        *,
        extracted_block_ids: Sequence[UUID] | None = None,
        ocr_block_ids: Sequence[UUID] | None = None,
        language_code: LanguageCode | None = None,
    ) -> list[LanguageBlockResult]:
        """Load viewer annotations without joining or returning source text."""
        statement = select(LanguageBlockResult).where(
            LanguageBlockResult.language_detection_run_id
            == language_detection_run_id
        )
        source_filter_requested = (
            extracted_block_ids is not None or ocr_block_ids is not None
        )
        source_predicates: list[object] = []
        if extracted_block_ids:
            source_predicates.append(
                LanguageBlockResult.extracted_block_id.in_(
                    extracted_block_ids
                )
            )
        if ocr_block_ids:
            source_predicates.append(
                LanguageBlockResult.ocr_block_id.in_(ocr_block_ids)
            )
        if source_filter_requested:
            if not source_predicates:
                return []
            statement = statement.where(or_(*source_predicates))
        if language_code is not None:
            statement = statement.where(
                LanguageBlockResult.language_code == language_code
            )
        rows = await self.session.scalars(
            statement.order_by(
                LanguageBlockResult.created_at,
                LanguageBlockResult.id,
            )
        )
        return list(rows.all())

    async def count(self, language_detection_run_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(LanguageBlockResult.id)).where(
                    LanguageBlockResult.language_detection_run_id
                    == language_detection_run_id
                )
            )
            or 0
        )

    async def average_confidence_by_language(
        self,
        language_detection_run_id: UUID,
    ) -> dict[str, float]:
        statement = (
            select(
                LanguageBlockResult.language_code,
                func.avg(LanguageBlockResult.confidence),
            )
            .where(
                LanguageBlockResult.language_detection_run_id
                == language_detection_run_id
            )
            .group_by(LanguageBlockResult.language_code)
        )
        rows = (await self.session.execute(statement)).all()
        return {
            code.value: float(average)
            for code, average in rows
            if average is not None
        }
