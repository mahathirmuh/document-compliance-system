"""Resolve effective OCR pages across immutable targeted re-OCR runs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_job import OCRJob
from app.models.ocr_page_result import OCRPageResult
from app.models.ocr_run import OCRRun, OCRRunStatus

_DEFAULT_MAXIMUM_DEPTH = 32
_USABLE_RUN_STATUSES = {
    OCRRunStatus.COMPLETED,
    OCRRunStatus.PARTIALLY_COMPLETED,
}


class OCRSourceChainError(RuntimeError):
    """An OCR ancestry link is malformed or crosses a source boundary."""


@dataclass(frozen=True, slots=True)
class EffectiveOCRRunPages:
    """The pages still owned by one immutable run."""

    run_id: UUID
    pages: tuple[OCRPageResult, ...]

    @property
    def page_numbers(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages)


@dataclass(frozen=True, slots=True)
class EffectiveOCRSourceChain:
    """Newest-page-wins view of one OCR run and its re-OCR ancestors."""

    latest_run_id: UUID
    run_ids: tuple[UUID, ...]
    pages_by_run: tuple[EffectiveOCRRunPages, ...]
    pages: tuple[OCRPageResult, ...]
    content_hash: str
    block_count: int


class OCRSourceChainService:
    """Build a safe effective OCR snapshot without copying ancestor rows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        maximum_depth: int = _DEFAULT_MAXIMUM_DEPTH,
    ) -> None:
        if maximum_depth < 1:
            raise ValueError("OCR source-chain depth must be positive.")
        self.session = session
        self.maximum_depth = maximum_depth

    async def resolve_by_id(
        self,
        ocr_run_id: UUID,
    ) -> EffectiveOCRSourceChain:
        run = await self.session.scalar(select(OCRRun).where(OCRRun.id == ocr_run_id))
        if run is None:
            raise OCRSourceChainError("The OCR source run does not exist.")
        return await self.resolve(run)

    async def resolve(
        self,
        latest_run: OCRRun,
    ) -> EffectiveOCRSourceChain:
        expected_file_id = latest_run.document_file_id
        expected_extraction_run_id = latest_run.source_extraction_run_id
        visited: set[UUID] = set()
        claimed_pages: dict[int, OCRPageResult] = {}
        page_groups: list[EffectiveOCRRunPages] = []
        run_ids: list[UUID] = []
        current = latest_run

        for _ in range(self.maximum_depth):
            if current.id in visited:
                raise OCRSourceChainError("The OCR source chain contains a cycle.")
            visited.add(current.id)
            run_ids.append(current.id)
            self._validate_source_boundary(
                current,
                document_file_id=expected_file_id,
                extraction_run_id=expected_extraction_run_id,
            )

            page_rows = tuple(
                (
                    await self.session.scalars(
                        select(OCRPageResult)
                        .where(OCRPageResult.ocr_run_id == current.id)
                        .order_by(
                            OCRPageResult.page_number,
                            OCRPageResult.id,
                        )
                    )
                ).all()
            )
            newly_claimed = tuple(
                page for page in page_rows if page.page_number not in claimed_pages
            )
            for page in newly_claimed:
                claimed_pages[page.page_number] = page
            if newly_claimed:
                page_groups.append(
                    EffectiveOCRRunPages(
                        run_id=current.id,
                        pages=newly_claimed,
                    )
                )

            source_run_id = await self._source_run_id(current)
            if source_run_id is None:
                return self._build_result(
                    latest_run_id=latest_run.id,
                    run_ids=run_ids,
                    page_groups=page_groups,
                    claimed_pages=claimed_pages,
                )
            if source_run_id in visited:
                raise OCRSourceChainError("The OCR source chain contains a cycle.")
            source_run = await self.session.scalar(
                select(OCRRun).where(OCRRun.id == source_run_id)
            )
            if source_run is None:
                raise OCRSourceChainError(
                    "The referenced OCR source run does not exist."
                )
            current = source_run

        raise OCRSourceChainError(
            "The OCR source chain exceeds the maximum supported depth."
        )

    async def _source_run_id(self, run: OCRRun) -> UUID | None:
        metadata = run.metadata_json or {}
        raw_source_id = metadata.get("sourceOcrRunId")
        if raw_source_id is None:
            summary = await self.session.scalar(
                select(OCRJob.result_summary_json).where(OCRJob.id == run.ocr_job_id)
            )
            if isinstance(summary, dict):
                raw_source_id = summary.get("sourceOcrRunId")
        if raw_source_id is None:
            return None
        try:
            return UUID(str(raw_source_id))
        except (TypeError, ValueError) as exc:
            raise OCRSourceChainError(
                "The OCR source chain contains an invalid run identifier."
            ) from exc

    @staticmethod
    def _validate_source_boundary(
        run: OCRRun,
        *,
        document_file_id: UUID,
        extraction_run_id: UUID,
    ) -> None:
        if (
            run.document_file_id != document_file_id
            or run.source_extraction_run_id != extraction_run_id
        ):
            raise OCRSourceChainError(
                "The OCR source chain crosses a document source boundary."
            )
        if run.status not in _USABLE_RUN_STATUSES:
            raise OCRSourceChainError("The OCR source chain contains an unusable run.")

    @staticmethod
    def _build_result(
        *,
        latest_run_id: UUID,
        run_ids: list[UUID],
        page_groups: list[EffectiveOCRRunPages],
        claimed_pages: dict[int, OCRPageResult],
    ) -> EffectiveOCRSourceChain:
        pages = tuple(
            claimed_pages[page_number] for page_number in sorted(claimed_pages)
        )
        combined_text = "\n".join(
            f"[PAGE {page.page_number}]\n{page.normalised_text}" for page in pages
        )
        return EffectiveOCRSourceChain(
            latest_run_id=latest_run_id,
            run_ids=tuple(run_ids),
            pages_by_run=tuple(page_groups),
            pages=pages,
            content_hash=hashlib.sha256(combined_text.encode("utf-8")).hexdigest(),
            block_count=sum(page.block_count for page in pages),
        )
