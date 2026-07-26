"""Bounded glossary result, summary, match, and finding queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.repositories.glossary_match_repository import (
    GlossaryMatchRepository,
)
from app.repositories.glossary_validation_repository import (
    GlossaryValidationRepository,
)
from app.schemas.glossary_validation import (
    GlossaryFindingListResponse,
    GlossaryFindingSignal,
    GlossaryMatchListResponse,
    GlossaryMatchResponse,
    GlossaryValidationRunResponse,
    GlossaryValidationSummaryResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.base import (
    GlossaryServiceBase,
    glossary_not_found,
)
from app.services.glossary.glossary_job_service import glossary_run_response


class GlossarySummaryService(GlossaryServiceBase):
    """Expose retained glossary results without unbounded relationship loads."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.runs = GlossaryValidationRepository(session)
        self.matches = GlossaryMatchRepository(session)

    async def run(
        self,
        run_id: UUID,
    ) -> GlossaryValidationRunResponse:
        return glossary_run_response(await self._run(run_id))

    async def summary(
        self,
        run_id: UUID,
    ) -> GlossaryValidationSummaryResponse:
        run = await self._run(run_id)
        counts = await self.matches.counts_for_run(run.id)
        finding_rows = (
            await self.session.execute(
                select(
                    ValidationFinding.finding_code,
                    func.count(ValidationFinding.id),
                )
                .where(
                    ValidationFinding.glossary_validation_run_id == run.id
                )
                .group_by(ValidationFinding.finding_code)
            )
        ).all()
        finding_counts = {
            code.value: int(count) for code, count in finding_rows
        }
        return GlossaryValidationSummaryResponse(
            run_id=run.id,
            status=run.status,
            total_terms=run.total_terms,
            matched_terms=run.matched_terms,
            preferred_term_matches=run.preferred_term_matches,
            forbidden_term_matches=run.forbidden_term_matches,
            missing_required_translations=(
                run.missing_required_translations
            ),
            inconsistent_terms=run.inconsistent_terms,
            exception_applied_count=run.exception_applied_count,
            total_findings=run.total_findings,
            match_count=int(counts["matchCount"]),
            language_counts=dict(counts["languageCounts"]),
            finding_counts=finding_counts,
            metrics=dict(run.metrics_json),
            warnings=list(run.warnings_json),
        )

    async def list_matches(
        self,
        run_id: UUID,
        *,
        page: int,
        page_size: int,
        **filters: object,
    ) -> GlossaryMatchListResponse:
        run = await self._run(run_id)
        items, total = await self.matches.list_page(
            run.id,
            page=page,
            page_size=page_size,
            **filters,
        )
        return GlossaryMatchListResponse(
            items=[
                GlossaryMatchResponse(
                    id=item.id,
                    glossary_validation_run_id=(
                        item.glossary_validation_run_id
                    ),
                    glossary_term_id=item.glossary_term_id,
                    glossary_translation_id=(
                        item.glossary_translation_id
                    ),
                    glossary_variant_id=item.glossary_variant_id,
                    term_code=item.term.term_code,
                    concept_name=item.term.concept_name,
                    language_code=item.language_code,
                    source_type=item.source_type,
                    extracted_block_id=item.extracted_block_id,
                    ocr_block_id=item.ocr_block_id,
                    container_id=item.container_id,
                    detected_section_id=item.detected_section_id,
                    source_reference=item.source_reference,
                    matched_text=item.matched_text,
                    normalised_matched_text=(
                        item.normalised_matched_text
                    ),
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                    match_type=item.match_type,
                    is_preferred=item.is_preferred,
                    is_forbidden=item.is_forbidden,
                    exception_id=item.exception_id,
                    metadata=dict(item.metadata_json),
                    created_at=item.created_at,
                )
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def list_findings(
        self,
        run_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> GlossaryFindingListResponse:
        run = await self._run(run_id)
        statement = (
            select(ValidationFinding)
            .where(
                ValidationFinding.glossary_validation_run_id == run.id
            )
            .order_by(
                ValidationFinding.created_at.desc(),
                ValidationFinding.id.desc(),
            )
        )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        items = (
            await self.session.scalars(
                statement.offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        return GlossaryFindingListResponse(
            items=[self._finding_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def _run(self, run_id: UUID):
        run = await self.runs.get_by_id(
            run_id,
            department_ids=self.department_ids,
        )
        if run is None:
            raise glossary_not_found("Glossary validation run")
        return run

    @staticmethod
    def _finding_response(
        item: ValidationFinding,
    ) -> GlossaryFindingSignal:
        metrics = dict(item.metrics_json)
        return GlossaryFindingSignal(
            id=item.id,
            finding_code=item.finding_code.value,
            severity=item.severity.value,
            status=item.status.value,
            title=item.title,
            description=item.description,
            recommendation=item.recommendation or "",
            glossary_term_id=UUID(str(metrics["glossaryTermId"])),
            language_code=item.language_code,
            source_reference=item.source_reference,
            extracted_block_id=item.extracted_block_id,
            ocr_block_id=item.ocr_block_id,
            translation_group_id=item.translation_group_id,
            exception_id=(
                UUID(str(metrics["glossaryExceptionId"]))
                if metrics.get("glossaryExceptionId")
                else None
            ),
            metrics=metrics,
            is_repeat=item.is_repeat,
            previous_finding_id=item.previous_finding_id,
            created_at=item.created_at,
        )
