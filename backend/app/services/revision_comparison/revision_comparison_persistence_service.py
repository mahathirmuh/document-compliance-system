"""Transactional persistence for official revision-comparison results."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from app.models.revision_change import (
    RevisionChange,
    RevisionChangeType,
)
from app.models.revision_comparison import (
    RevisionComparison,
    RevisionComparisonClassification,
    RevisionComparisonStatus,
)
from app.models.revision_comparison_job import RevisionComparisonJob
from app.repositories.revision_change_repository import (
    RevisionChangeRepository,
)
from app.repositories.revision_comparison_repository import (
    RevisionComparisonRepository,
)
from app.services.revision_comparison.revision_alignment_service import (
    AlignedRevisionPair,
)
from app.services.revision_comparison.revision_change_detection_service import (
    DetectedRevisionChange,
)
from app.services.revision_comparison.revision_context_service import (
    RevisionContext,
)
from app.utils.datetime import utc_now


class RevisionComparisonPersistenceService:
    def __init__(
        self,
        comparisons: RevisionComparisonRepository,
        changes: RevisionChangeRepository,
        *,
        batch_size: int = 1000,
    ) -> None:
        self.comparisons = comparisons
        self.changes = changes
        self.batch_size = max(1, batch_size)

    async def persist(
        self,
        *,
        job: RevisionComparisonJob,
        base: RevisionContext,
        target: RevisionContext,
        pairs: list[AlignedRevisionPair],
        detected_changes: list[DetectedRevisionChange],
        language_summary: list[dict[str, object]],
        finding_changes: list[dict[str, object]],
        finding_summary: dict[str, int],
        classification: RevisionComparisonClassification,
        warnings: list[str],
    ) -> RevisionComparison:
        counts = Counter(item.change_type for item in detected_changes)
        changed_total = sum(
            counts[item]
            for item in RevisionChangeType
            if item is not RevisionChangeType.UNCHANGED
        )
        comparison = RevisionComparison(
            revision_comparison_job_id=job.id,
            document_id=job.document_id,
            base_revision_id=job.base_revision_id,
            target_revision_id=job.target_revision_id,
            base_document_file_id=job.base_document_file_id,
            target_document_file_id=job.target_document_file_id,
            base_extraction_run_id=base.extraction_run_id,
            target_extraction_run_id=target.extraction_run_id,
            base_compliance_run_id=base.compliance_run_id,
            target_compliance_run_id=target.compliance_run_id,
            base_similarity_run_id=base.similarity_run_id,
            target_similarity_run_id=target.similarity_run_id,
            base_glossary_run_id=base.glossary_run_id,
            target_glossary_run_id=target.glossary_run_id,
            status=(
                RevisionComparisonStatus.PARTIALLY_COMPLETED
                if warnings
                else RevisionComparisonStatus.COMPLETED
            ),
            classification=classification,
            base_content_hash=base.content_hash,
            target_content_hash=target.content_hash,
            total_changes=changed_total,
            added_blocks=counts[RevisionChangeType.ADDED],
            removed_blocks=counts[RevisionChangeType.REMOVED],
            modified_blocks=(
                counts[RevisionChangeType.MODIFIED]
                + counts[RevisionChangeType.SPLIT]
                + counts[RevisionChangeType.MERGED]
            ),
            moved_blocks=counts[RevisionChangeType.MOVED],
            unchanged_blocks=counts[RevisionChangeType.UNCHANGED],
            added_sections=self._section_count(
                pairs, detected_changes, RevisionChangeType.ADDED
            ),
            removed_sections=self._section_count(
                pairs, detected_changes, RevisionChangeType.REMOVED
            ),
            modified_sections=self._section_count(
                pairs, detected_changes, RevisionChangeType.MODIFIED
            ),
            added_translation_groups=self._group_count(
                pairs, detected_changes, RevisionChangeType.ADDED
            ),
            removed_translation_groups=self._group_count(
                pairs, detected_changes, RevisionChangeType.REMOVED
            ),
            modified_translation_groups=self._group_count(
                pairs, detected_changes, RevisionChangeType.MODIFIED
            ),
            language_coverage_change_json={
                "languages": language_summary,
                "baseCoverageBasis": base.language_coverage_basis,
                "targetCoverageBasis": target.language_coverage_basis,
            },
            compliance_score_change=self._delta(
                base.compliance_score, target.compliance_score
            ),
            similarity_score_change=self._delta(
                base.similarity_score, target.similarity_score
            ),
            new_findings=finding_summary.get("NEW", 0),
            removed_findings=finding_summary.get(
                "NO_LONGER_REPRODUCED", 0
            ),
            repeated_findings=finding_summary.get("REPEATED", 0)
            + finding_summary.get("UNCHANGED", 0),
            severity_change_count=finding_summary.get(
                "SEVERITY_INCREASED", 0
            )
            + finding_summary.get("SEVERITY_DECREASED", 0),
            summary_json={
                "classification": classification.value,
                "languageChanges": language_summary,
                "findingChanges": finding_changes,
                "findingSummary": finding_summary,
                "baseComplianceStatus": base.compliance_status,
                "targetComplianceStatus": target.compliance_status,
                "glossaryViolationChange": self._delta(
                    base.glossary_violation_count,
                    target.glossary_violation_count,
                ),
                "openFindingChange": (
                    target.open_finding_count - base.open_finding_count
                ),
                "criticalFindingChange": (
                    target.critical_open_finding_count
                    - base.critical_open_finding_count
                ),
                "comparisonDisclaimer": (
                    "Automated alignment is a review aid and does not prove "
                    "legal or technical equivalence."
                ),
            },
            warnings_json=warnings,
            requested_by=job.requested_by,
            started_at=job.started_at,
            completed_at=utc_now(),
        )
        await self.comparisons.add(comparison)
        rows = [
            self._change_model(comparison.id, pair, change)
            for pair, change in zip(pairs, detected_changes, strict=True)
        ]
        for offset in range(0, len(rows), self.batch_size):
            await self.changes.bulk_add(
                rows[offset : offset + self.batch_size]
            )
        return comparison

    @staticmethod
    def _change_model(
        comparison_id: UUID,
        pair: AlignedRevisionPair,
        change: DetectedRevisionChange,
    ) -> RevisionChange:
        base = pair.base
        target = pair.target
        return RevisionChange(
            revision_comparison_id=comparison_id,
            change_type=change.change_type,
            entity_type=change.entity_type,
            base_container_id=base.container_id if base else None,
            target_container_id=target.container_id if target else None,
            base_section_id=base.section_id if base else None,
            target_section_id=target.section_id if target else None,
            base_translation_group_id=(
                base.translation_group_id if base else None
            ),
            target_translation_group_id=(
                target.translation_group_id if target else None
            ),
            base_block_id=change.base_id,
            target_block_id=change.target_id,
            language_code=change.language_code,
            source_reference_base=change.source_reference_base,
            source_reference_target=change.source_reference_target,
            base_text_snapshot=change.base_text_snapshot,
            target_text_snapshot=change.target_text_snapshot,
            text_similarity=change.text_similarity,
            structural_similarity=change.structural_similarity,
            alignment_confidence=change.alignment_confidence,
            character_change_count=change.character_change_count,
            word_change_count=change.word_change_count,
            metadata_json=change.metadata,
        )

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return right - left

    @staticmethod
    def _section_count(
        pairs: list[AlignedRevisionPair],
        changes: list[DetectedRevisionChange],
        change_type: RevisionChangeType,
    ) -> int:
        base_sections = {
            pair.base.section_code
            for pair in pairs
            if pair.base is not None and pair.base.section_code
        }
        target_sections = {
            pair.target.section_code
            for pair in pairs
            if pair.target is not None and pair.target.section_code
        }
        if change_type is RevisionChangeType.ADDED:
            return len(target_sections - base_sections)
        if change_type is RevisionChangeType.REMOVED:
            return len(base_sections - target_sections)
        changed_types = {
            RevisionChangeType.MODIFIED,
            RevisionChangeType.MOVED,
            RevisionChangeType.SPLIT,
            RevisionChangeType.MERGED,
        }
        return len(
            {
                str(
                    item.metadata.get("targetSectionCode")
                    or item.metadata.get("baseSectionCode")
                )
                for item in changes
                if item.change_type in changed_types
                and (
                    item.metadata.get("targetSectionCode")
                    or item.metadata.get("baseSectionCode")
                )
            }
            & base_sections
            & target_sections
        )

    @staticmethod
    def _group_count(
        pairs: list[AlignedRevisionPair],
        changes: list[DetectedRevisionChange],
        change_type: RevisionChangeType,
    ) -> int:
        group_ids: set[UUID] = set()
        modified_types = {
            RevisionChangeType.MODIFIED,
            RevisionChangeType.MOVED,
            RevisionChangeType.SPLIT,
            RevisionChangeType.MERGED,
        }
        for pair, change in zip(pairs, changes, strict=True):
            if change_type is RevisionChangeType.ADDED:
                if (
                    change.change_type is RevisionChangeType.ADDED
                    and pair.target is not None
                    and pair.target.translation_group_id is not None
                ):
                    group_ids.add(pair.target.translation_group_id)
            elif change_type is RevisionChangeType.REMOVED:
                if (
                    change.change_type is RevisionChangeType.REMOVED
                    and pair.base is not None
                    and pair.base.translation_group_id is not None
                ):
                    group_ids.add(pair.base.translation_group_id)
            elif change.change_type in modified_types:
                group_id = (
                    pair.target.translation_group_id
                    if pair.target is not None
                    else (
                        pair.base.translation_group_id
                        if pair.base is not None
                        else None
                    )
                )
                if group_id is not None:
                    group_ids.add(group_id)
        return len(group_ids)
