"""Document and section aggregation over retained pairwise signals."""

from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from uuid import UUID

from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    SimilarityRunStatus,
)
from app.schemas.similarity_internal import (
    SectionSimilarityDraft,
    SimilarityAggregate,
    SimilarityContext,
    SimilarityResultDraft,
)

_CATEGORY_RANK = {
    SimilarityCategory.NOT_EVALUATED: 0,
    SimilarityCategory.HIGH: 1,
    SimilarityCategory.ACCEPTABLE: 2,
    SimilarityCategory.NEEDS_REVIEW: 3,
    SimilarityCategory.LOW: 4,
}


class SimilarityAggregationService:
    def aggregate(
        self,
        context: SimilarityContext,
        results: list[SimilarityResultDraft],
    ) -> SimilarityAggregate:
        completed = [
            item
            for item in results
            if item.analysis_status is SimilarityAnalysisStatus.COMPLETED
            and item.similarity_score is not None
        ]
        scores = [
            float(item.similarity_score)
            for item in completed
            if item.similarity_score is not None
        ]
        group_results: dict[UUID, list[SimilarityResultDraft]] = defaultdict(list)
        for item in results:
            group_results[item.translation_group_id].append(item)
        eligible_groups = {
            item.translation_group_id for item in completed
        }
        groups_with_failed_pairs = {
            item.translation_group_id
            for item in results
            if item.analysis_status is SimilarityAnalysisStatus.FAILED
        }
        failed_groups = groups_with_failed_pairs - eligible_groups
        category_counts = {
            SimilarityCategory.HIGH: 0,
            SimilarityCategory.ACCEPTABLE: 0,
            SimilarityCategory.NEEDS_REVIEW: 0,
            SimilarityCategory.LOW: 0,
            SimilarityCategory.NOT_EVALUATED: 0,
        }
        for group in context.groups:
            items = group_results.get(group.id, [])
            category = (
                max(
                    (item.similarity_category for item in items),
                    key=lambda value: _CATEGORY_RANK[value],
                )
                if items
                else SimilarityCategory.NOT_EVALUATED
            )
            category_counts[category] += 1
        pair_averages: dict[str, float | None] = {}
        for source, target in (("id", "en"), ("id", "zh"), ("en", "zh")):
            pair_scores = [
                float(item.similarity_score)
                for item in completed
                if item.source_language_code == source
                and item.target_language_code == target
                and item.similarity_score is not None
            ]
            pair_averages[f"{source}-{target}"] = (
                round(fmean(pair_scores), 6) if pair_scores else None
            )
        mismatch_counts = {
            "number": self._mismatch_count(
                results, "number_consistency"
            ),
            "date": self._mismatch_count(results, "date_consistency"),
            "measurement": self._mismatch_count(
                results, "measurement_consistency"
            ),
            "reference": self._mismatch_count(
                results, "reference_consistency"
            ),
            "negation": sum(
                item.negation_consistency.status
                in {
                    ConsistencyStatus.MISMATCH,
                    ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH,
                }
                for item in results
            ),
        }
        if groups_with_failed_pairs and not scores:
            status = SimilarityRunStatus.FAILED
        elif groups_with_failed_pairs:
            status = SimilarityRunStatus.PARTIALLY_COMPLETED
        else:
            status = SimilarityRunStatus.COMPLETED
        total = len(context.groups)
        analysed = len(eligible_groups)
        return SimilarityAggregate(
            status=status,
            translation_group_count=total,
            eligible_group_count=analysed,
            analysed_group_count=analysed,
            skipped_group_count=max(0, total - analysed - len(failed_groups)),
            failed_group_count=len(failed_groups),
            average_similarity=round(fmean(scores), 6) if scores else None,
            minimum_similarity=round(min(scores), 6) if scores else None,
            maximum_similarity=round(max(scores), 6) if scores else None,
            pair_averages=pair_averages,
            high_similarity_groups=category_counts[SimilarityCategory.HIGH],
            review_similarity_groups=(
                category_counts[SimilarityCategory.NEEDS_REVIEW]
                + category_counts[SimilarityCategory.ACCEPTABLE]
            ),
            low_similarity_groups=category_counts[SimilarityCategory.LOW],
            unavailable_similarity_groups=category_counts[
                SimilarityCategory.NOT_EVALUATED
            ],
            mismatch_counts=mismatch_counts,
            metrics={
                "pairResultCount": len(results),
                "completedPairCount": len(completed),
                "categoryCounts": {
                    key.value: value
                    for key, value in category_counts.items()
                },
            },
        )

    def sections(
        self,
        context: SimilarityContext,
        results: list[SimilarityResultDraft],
    ) -> list[SectionSimilarityDraft]:
        groups_by_section: dict[
            tuple[UUID | None, str], set[UUID]
        ] = defaultdict(set)
        for group in context.groups:
            key = (
                group.detected_section_id,
                group.canonical_section_code or "UNASSIGNED",
            )
            groups_by_section[key].add(group.id)
        results_by_section: dict[
            tuple[UUID | None, str], list[SimilarityResultDraft]
        ] = defaultdict(list)
        for item in results:
            key = (
                item.detected_section_id,
                item.canonical_section_code or "UNASSIGNED",
            )
            results_by_section[key].append(item)
        output: list[SectionSimilarityDraft] = []
        for key, group_ids in sorted(
            groups_by_section.items(), key=lambda item: item[0][1]
        ):
            items = results_by_section.get(key, [])
            completed = [
                item
                for item in items
                if item.analysis_status is SimilarityAnalysisStatus.COMPLETED
                and item.similarity_score is not None
            ]
            scores = [
                float(item.similarity_score)
                for item in completed
                if item.similarity_score is not None
            ]
            eligible_group_ids = {
                item.translation_group_id for item in completed
            }
            pair_summary: dict[str, dict[str, float | int | None]] = {}
            for source, target in (
                ("id", "en"),
                ("id", "zh"),
                ("en", "zh"),
            ):
                pair_scores = [
                    float(item.similarity_score)
                    for item in completed
                    if item.source_language_code == source
                    and item.target_language_code == target
                    and item.similarity_score is not None
                ]
                pair_summary[f"{source}-{target}"] = {
                    "count": len(pair_scores),
                    "average": (
                        round(fmean(pair_scores), 6)
                        if pair_scores
                        else None
                    ),
                }
            output.append(
                SectionSimilarityDraft(
                    detected_section_id=key[0],
                    canonical_section_code=key[1],
                    total_groups=len(group_ids),
                    eligible_groups=len(eligible_group_ids),
                    analysed_groups=len(eligible_group_ids),
                    average_similarity=(
                        round(fmean(scores), 6) if scores else None
                    ),
                    minimum_similarity=(
                        round(min(scores), 6) if scores else None
                    ),
                    low_similarity_groups=len(
                        {
                            item.translation_group_id
                            for item in items
                            if item.similarity_category
                            is SimilarityCategory.LOW
                        }
                    ),
                    number_mismatches=self._mismatch_count(
                        items, "number_consistency"
                    ),
                    date_mismatches=self._mismatch_count(
                        items, "date_consistency"
                    ),
                    measurement_mismatches=self._mismatch_count(
                        items, "measurement_consistency"
                    ),
                    reference_mismatches=self._mismatch_count(
                        items, "reference_consistency"
                    ),
                    negation_mismatches=sum(
                        item.negation_consistency.status
                        in {
                            ConsistencyStatus.MISMATCH,
                            ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH,
                        }
                        for item in items
                    ),
                    pairwise_summary=pair_summary,
                    metrics={"pairResultCount": len(items)},
                )
            )
        return output

    @staticmethod
    def _mismatch_count(
        results: list[SimilarityResultDraft],
        field: str,
    ) -> int:
        return sum(
            getattr(item, field).status is ConsistencyStatus.MISMATCH
            for item in results
        )
