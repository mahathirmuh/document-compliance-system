"""Persistence and bounded queries for pairwise similarity evidence."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_enums import FindingSeverity
from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityCategory,
)
from app.models.similarity_result import TranslationSimilarityResult
from app.models.translation_group_member import TranslationGroupMember
from app.models.validation_finding import ValidationFinding


class TranslationSimilarityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        results: Sequence[TranslationSimilarityResult],
        *,
        batch_size: int = 500,
    ) -> list[TranslationSimilarityResult]:
        items = list(results)
        for offset in range(0, len(items), max(1, batch_size)):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def list_for_run(
        self,
        run_id: UUID,
        *,
        section_id: UUID | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
        similarity_category: SimilarityCategory | None = None,
        minimum_score: float | None = None,
        maximum_score: float | None = None,
        has_number_mismatch: bool | None = None,
        has_date_mismatch: bool | None = None,
        has_measurement_mismatch: bool | None = None,
        has_reference_mismatch: bool | None = None,
        has_negation_mismatch: bool | None = None,
        finding_severity: FindingSeverity | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[TranslationSimilarityResult], int]:
        predicates: list[object] = [
            TranslationSimilarityResult.similarity_run_id == run_id
        ]
        if section_id is not None:
            predicates.append(
                TranslationSimilarityResult.detected_section_id == section_id
            )
        if source_language is not None:
            predicates.append(
                TranslationSimilarityResult.source_language_code
                == source_language.casefold()
            )
        if target_language is not None:
            predicates.append(
                TranslationSimilarityResult.target_language_code
                == target_language.casefold()
            )
        if similarity_category is not None:
            predicates.append(
                TranslationSimilarityResult.similarity_category
                == similarity_category
            )
        if minimum_score is not None:
            predicates.append(
                TranslationSimilarityResult.similarity_score >= minimum_score
            )
        if maximum_score is not None:
            predicates.append(
                TranslationSimilarityResult.similarity_score <= maximum_score
            )
        self._mismatch_predicate(
            predicates,
            TranslationSimilarityResult.number_consistency_status,
            has_number_mismatch,
        )
        self._mismatch_predicate(
            predicates,
            TranslationSimilarityResult.date_consistency_status,
            has_date_mismatch,
        )
        self._mismatch_predicate(
            predicates,
            TranslationSimilarityResult.measurement_consistency_status,
            has_measurement_mismatch,
        )
        self._mismatch_predicate(
            predicates,
            TranslationSimilarityResult.reference_consistency_status,
            has_reference_mismatch,
        )
        if has_negation_mismatch is True:
            predicates.append(
                TranslationSimilarityResult.negation_consistency_status.in_(
                    (
                        ConsistencyStatus.MISMATCH,
                        ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH,
                    )
                )
            )
        elif has_negation_mismatch is False:
            predicates.append(
                TranslationSimilarityResult.negation_consistency_status.not_in(
                    (
                        ConsistencyStatus.MISMATCH,
                        ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH,
                    )
                )
            )
        if finding_severity is not None:
            predicates.append(
                exists(
                    select(ValidationFinding.id).where(
                        ValidationFinding.similarity_run_id == run_id,
                        ValidationFinding.translation_group_id
                        == TranslationSimilarityResult.translation_group_id,
                        ValidationFinding.severity == finding_severity,
                    )
                )
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            predicates.append(
                or_(
                    TranslationSimilarityResult.source_reference.ilike(
                        pattern
                    ),
                    TranslationSimilarityResult.source_language_code.ilike(
                        pattern
                    ),
                    TranslationSimilarityResult.target_language_code.ilike(
                        pattern
                    ),
                    exists(
                        select(TranslationGroupMember.id).where(
                            TranslationGroupMember.id.in_(
                                (
                                    TranslationSimilarityResult.source_member_id,
                                    TranslationSimilarityResult.target_member_id,
                                )
                            ),
                            TranslationGroupMember.text_snapshot.ilike(pattern),
                        )
                    ),
                )
            )
        statement = select(TranslationSimilarityResult).where(*predicates)
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(statement.subquery())
                )
            )
            or 0
        )
        rows = await self.session.scalars(
            statement.order_by(
                TranslationSimilarityResult.source_reference,
                TranslationSimilarityResult.source_language_code,
                TranslationSimilarityResult.target_language_code,
                TranslationSimilarityResult.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.all()), total

    async def member_text_snapshots(
        self,
        member_ids: Sequence[UUID],
    ) -> dict[UUID, str]:
        ids = list(dict.fromkeys(member_ids))
        if not ids:
            return {}
        rows = await self.session.execute(
            select(
                TranslationGroupMember.id,
                TranslationGroupMember.text_snapshot,
            ).where(TranslationGroupMember.id.in_(ids))
        )
        return {member_id: text for member_id, text in rows.all()}

    async def finding_ids_by_group(
        self,
        *,
        run_id: UUID,
        group_ids: Sequence[UUID],
    ) -> dict[UUID, list[UUID]]:
        ids = list(dict.fromkeys(group_ids))
        if not ids:
            return {}
        rows = await self.session.execute(
            select(
                ValidationFinding.translation_group_id,
                ValidationFinding.id,
            )
            .where(
                ValidationFinding.similarity_run_id == run_id,
                ValidationFinding.translation_group_id.in_(ids),
            )
            .order_by(
                ValidationFinding.translation_group_id,
                ValidationFinding.created_at,
                ValidationFinding.id,
            )
        )
        grouped: dict[UUID, list[UUID]] = {}
        for group_id, finding_id in rows.all():
            if group_id is not None:
                grouped.setdefault(group_id, []).append(finding_id)
        return grouped

    async def count_for_run(self, run_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(TranslationSimilarityResult.id)).where(
                        TranslationSimilarityResult.similarity_run_id == run_id
                    )
                )
            )
            or 0
        )

    @staticmethod
    def _mismatch_predicate(
        predicates: list[object],
        column: object,
        selected: bool | None,
    ) -> None:
        if selected is True:
            predicates.append(column == ConsistencyStatus.MISMATCH)
        elif selected is False:
            predicates.append(column != ConsistencyStatus.MISMATCH)
