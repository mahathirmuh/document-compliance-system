"""Scoped reads and public DTO mapping for similarity evidence."""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.compliance_enums import FindingSeverity
from app.models.similarity_enums import SimilarityCategory
from app.models.similarity_result import TranslationSimilarityResult
from app.models.similarity_run import SimilarityRun
from app.models.similarity_section_summary import SectionSimilaritySummary
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.section_similarity_repository import (
    SectionSimilarityRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.repositories.translation_similarity_repository import (
    TranslationSimilarityRepository,
)
from app.schemas.similarity import (
    SectionSimilaritySummaryListResponse,
    SectionSimilaritySummaryResponse,
    SimilarityRunListResponse,
    SimilarityRunResponse,
    SimilaritySummaryResponse,
    TranslationSimilarityResultListResponse,
    TranslationSimilarityResultResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.similarity.similarity_job_service import (
    similarity_run_not_found,
)


class SimilarityQueryService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.settings = settings
        self.user = user
        self.metadata = metadata
        self.runs = SimilarityRunRepository(session)
        self.results = TranslationSimilarityRepository(session)
        self.sections = SectionSimilarityRepository(session)
        self.audits = AuditLogRepository(session)

    async def get_run(self, run_id: UUID) -> SimilarityRunResponse:
        return similarity_run_response(await self._run(run_id))

    async def summary(self, run_id: UUID) -> SimilaritySummaryResponse:
        run = await self._run(run_id)
        section_count = await self.sections.count_for_run(run.id)
        metrics = dict(run.metrics_json or {})
        stored_category_counts = metrics.get("categoryCounts")
        if not isinstance(stored_category_counts, dict):
            stored_category_counts = {}
        category_counts = {
            category.value: int(stored_category_counts.get(category.value, 0) or 0)
            for category in SimilarityCategory
        }
        if not stored_category_counts:
            category_counts.update(
                {
                    SimilarityCategory.HIGH.value: run.high_similarity_groups,
                    SimilarityCategory.NEEDS_REVIEW.value: (
                        run.review_similarity_groups
                    ),
                    SimilarityCategory.LOW.value: run.low_similarity_groups,
                    SimilarityCategory.NOT_EVALUATED.value: (
                        run.unavailable_similarity_groups
                    ),
                }
            )
        return SimilaritySummaryResponse(
            run_id=run.id,
            status=run.status,
            average_similarity=_optional_float(run.average_similarity),
            minimum_similarity=_optional_float(run.minimum_similarity),
            maximum_similarity=_optional_float(run.maximum_similarity),
            translation_group_count=run.translation_group_count,
            eligible_group_count=run.eligible_group_count,
            analysed_group_count=run.analysed_group_count,
            skipped_group_count=run.skipped_group_count,
            failed_group_count=run.failed_group_count,
            categories=category_counts,
            pair_averages={
                "id-en": _optional_float(run.id_en_average_similarity),
                "id-zh": _optional_float(run.id_zh_average_similarity),
                "en-zh": _optional_float(run.en_zh_average_similarity),
            },
            mismatches={
                "number": run.number_mismatch_count,
                "date": run.date_mismatch_count,
                "measurement": run.measurement_mismatch_count,
                "reference": run.reference_mismatch_count,
                "negation": run.negation_mismatch_count,
            },
            section_count=section_count,
            finding_count=int(metrics.get("findingCount", 0) or 0),
            warnings=list(run.warnings_json or []),
        )

    async def list_results(
        self,
        run_id: UUID,
        *,
        section_id: UUID | None,
        source_language: str | None,
        target_language: str | None,
        similarity_category: SimilarityCategory | None,
        minimum_score: float | None,
        maximum_score: float | None,
        has_number_mismatch: bool | None,
        has_date_mismatch: bool | None,
        has_measurement_mismatch: bool | None,
        has_reference_mismatch: bool | None,
        has_negation_mismatch: bool | None,
        finding_severity: FindingSeverity | None = None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> TranslationSimilarityResultListResponse:
        await self._run(run_id)
        items, total = await self.results.list_for_run(
            run_id,
            section_id=section_id,
            source_language=source_language,
            target_language=target_language,
            similarity_category=similarity_category,
            minimum_score=minimum_score,
            maximum_score=maximum_score,
            has_number_mismatch=has_number_mismatch,
            has_date_mismatch=has_date_mismatch,
            has_measurement_mismatch=has_measurement_mismatch,
            has_reference_mismatch=has_reference_mismatch,
            has_negation_mismatch=has_negation_mismatch,
            finding_severity=finding_severity,
            search=search,
            page=page,
            page_size=page_size,
        )
        member_ids = [
            member_id
            for item in items
            for member_id in (
                item.source_member_id,
                item.target_member_id,
            )
            if member_id is not None
        ]
        member_texts = await self.results.member_text_snapshots(member_ids)
        finding_ids = await self.results.finding_ids_by_group(
            run_id=run_id,
            group_ids=[item.translation_group_id for item in items],
        )
        return TranslationSimilarityResultListResponse(
            items=[
                similarity_result_response(
                    item,
                    member_texts=member_texts,
                    finding_ids=finding_ids.get(
                        item.translation_group_id,
                        [],
                    ),
                    snippet_max_characters=(
                        self.settings.similarity_snippet_max_characters
                    ),
                )
                for item in items
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_sections(
        self,
        run_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> SectionSimilaritySummaryListResponse:
        await self._run(run_id)
        items, total = await self.sections.list_for_run(
            run_id, page=page, page_size=page_size
        )
        return SectionSimilaritySummaryListResponse(
            items=[section_similarity_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def latest_for_file(
        self, file_id: UUID
    ) -> SimilarityRunResponse:
        self._ensure_view()
        run = await self.runs.get_latest_for_file(
            file_id, department_ids=self._scope_department_ids()
        )
        if run is None:
            raise similarity_run_not_found()
        return similarity_run_response(run)

    async def history_for_file(
        self,
        file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> SimilarityRunListResponse:
        self._ensure_view()
        items, total = await self.runs.list_for_file(
            file_id,
            department_ids=self._scope_department_ids(),
            page=page,
            page_size=page_size,
        )
        return SimilarityRunListResponse(
            items=[similarity_run_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def _run(self, run_id: UUID) -> SimilarityRun:
        self._ensure_view()
        run = await self.runs.get_by_id(
            run_id, department_ids=self._scope_department_ids()
        )
        if run is None:
            raise similarity_run_not_found()
        return run

    def _ensure_view(self) -> None:
        if not has_permission(
            self.user.role,
            Permission.SIMILARITY_VIEW,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()

    def _scope_department_ids(self) -> Sequence[UUID] | None:
        if has_permission(
            self.user.role,
            Permission.SIMILARITY_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        ):
            return None
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department assignment is required for similarity access."
            )
        return [self.user.department_id]


def similarity_run_response(run: SimilarityRun) -> SimilarityRunResponse:
    document = run.document
    revision = run.revision
    document_file = run.document_file
    requester = run.requester
    return SimilarityRunResponse(
        id=run.id,
        similarity_job_id=run.similarity_job_id,
        document_id=run.document_id,
        document_revision_id=run.document_revision_id,
        document_file_id=run.document_file_id,
        compliance_run_id=run.compliance_run_id,
        language_detection_run_id=run.language_detection_run_id,
        document={
            "id": document.id,
            "base_document_code": document.base_document_code,
            "title": document.title,
            "department_id": document.department_id,
        },
        revision={
            "id": revision.id,
            "revision_code": revision.revision_code,
            "full_document_code": revision.full_document_code,
        },
        file={
            "id": document_file.id,
            "filename": document_file.original_filename,
            "file_extension": document_file.file_extension,
        },
        provider=run.provider,
        model_name=run.model_name,
        model_version=run.model_version,
        status=run.status,
        source_content_hash=run.source_content_hash,
        translation_group_count=run.translation_group_count,
        eligible_group_count=run.eligible_group_count,
        analysed_group_count=run.analysed_group_count,
        skipped_group_count=run.skipped_group_count,
        failed_group_count=run.failed_group_count,
        average_similarity=_optional_float(run.average_similarity),
        minimum_similarity=_optional_float(run.minimum_similarity),
        maximum_similarity=_optional_float(run.maximum_similarity),
        id_en_average_similarity=_optional_float(
            run.id_en_average_similarity
        ),
        id_zh_average_similarity=_optional_float(
            run.id_zh_average_similarity
        ),
        en_zh_average_similarity=_optional_float(
            run.en_zh_average_similarity
        ),
        high_similarity_groups=run.high_similarity_groups,
        review_similarity_groups=run.review_similarity_groups,
        low_similarity_groups=run.low_similarity_groups,
        unavailable_similarity_groups=run.unavailable_similarity_groups,
        number_mismatch_count=run.number_mismatch_count,
        date_mismatch_count=run.date_mismatch_count,
        measurement_mismatch_count=run.measurement_mismatch_count,
        reference_mismatch_count=run.reference_mismatch_count,
        negation_mismatch_count=run.negation_mismatch_count,
        warnings=list(run.warnings_json or []),
        metrics=dict(run.metrics_json or {}),
        started_at=run.started_at,
        completed_at=run.completed_at,
        requested_by=(
            {"id": requester.id, "name": requester.name}
            if requester is not None
            else None
        ),
        created_at=run.created_at,
    )


def similarity_result_response(
    result: TranslationSimilarityResult,
    *,
    member_texts: dict[UUID, str] | None = None,
    finding_ids: Sequence[UUID] = (),
    snippet_max_characters: int = 500,
) -> TranslationSimilarityResultResponse:
    texts = member_texts or {}
    metrics = dict(result.metrics_json or {})
    return TranslationSimilarityResultResponse(
        id=result.id,
        similarity_run_id=result.similarity_run_id,
        translation_group_id=result.translation_group_id,
        detected_section_id=result.detected_section_id,
        container_id=result.container_id,
        source_reference=result.source_reference,
        source_language_code=result.source_language_code,
        target_language_code=result.target_language_code,
        source_member_id=result.source_member_id,
        target_member_id=result.target_member_id,
        source_text_hash=result.source_text_hash,
        target_text_hash=result.target_text_hash,
        source_text_snippet=_snippet(
            texts.get(result.source_member_id),
            snippet_max_characters,
        ),
        target_text_snippet=_snippet(
            texts.get(result.target_member_id),
            snippet_max_characters,
        ),
        similarity_score=_optional_float(result.similarity_score),
        similarity_category=result.similarity_category,
        confidence=float(result.confidence),
        structural_group_confidence=_optional_score(
            metrics.get("groupConfidence")
        ),
        ocr_confidence=_optional_score(metrics.get("ocrConfidence")),
        analysis_status=result.analysis_status,
        source_character_count=result.source_character_count,
        target_character_count=result.target_character_count,
        length_ratio=_optional_float(result.length_ratio),
        number_consistency_status=result.number_consistency_status,
        date_consistency_status=result.date_consistency_status,
        measurement_consistency_status=(
            result.measurement_consistency_status
        ),
        reference_consistency_status=result.reference_consistency_status,
        negation_consistency_status=result.negation_consistency_status,
        number_details=dict(result.number_details_json or {}),
        date_details=dict(result.date_details_json or {}),
        measurement_details=dict(result.measurement_details_json or {}),
        reference_details=dict(result.reference_details_json or {}),
        negation_details=dict(result.negation_details_json or {}),
        chunk_count_source=result.chunk_count_source,
        chunk_count_target=result.chunk_count_target,
        metrics=metrics,
        warnings=list(result.warnings_json or []),
        finding_count=len(finding_ids),
        related_finding_ids=list(finding_ids),
        created_at=result.created_at,
    )


def section_similarity_response(
    summary: SectionSimilaritySummary,
) -> SectionSimilaritySummaryResponse:
    return SectionSimilaritySummaryResponse(
        id=summary.id,
        similarity_run_id=summary.similarity_run_id,
        detected_section_id=summary.detected_section_id,
        canonical_section_code=summary.canonical_section_code,
        total_groups=summary.total_groups,
        eligible_groups=summary.eligible_groups,
        analysed_groups=summary.analysed_groups,
        average_similarity=_optional_float(summary.average_similarity),
        minimum_similarity=_optional_float(summary.minimum_similarity),
        low_similarity_groups=summary.low_similarity_groups,
        number_mismatches=summary.number_mismatches,
        date_mismatches=summary.date_mismatches,
        measurement_mismatches=summary.measurement_mismatches,
        reference_mismatches=summary.reference_mismatches,
        negation_mismatches=summary.negation_mismatches,
        pairwise_summary=dict(summary.pairwise_summary_json or {}),
        metrics=dict(summary.metrics_json or {}),
        created_at=summary.created_at,
    )


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _optional_score(value: object) -> float | None:
    try:
        score = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return score if score is not None and 0 <= score <= 1 else None


def _snippet(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= maximum:
        return normalized
    return f"{normalized[: maximum - 1].rstrip()}…"
