"""Aggregate revision changes by canonical section provenance."""

from __future__ import annotations

from collections import defaultdict

from app.models.revision_change import RevisionChangeType
from app.services.revision_comparison.revision_change_detection_service import (
    DetectedRevisionChange,
)


class RevisionSectionComparisonService:
    def summarize(
        self, changes: list[DetectedRevisionChange]
    ) -> list[dict[str, object]]:
        grouped: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "added": 0,
                "removed": 0,
                "modified": 0,
                "moved": 0,
                "unchanged": 0,
            }
        )
        field_by_type = {
            RevisionChangeType.ADDED: "added",
            RevisionChangeType.REMOVED: "removed",
            RevisionChangeType.MODIFIED: "modified",
            RevisionChangeType.MOVED: "moved",
            RevisionChangeType.UNCHANGED: "unchanged",
            RevisionChangeType.SPLIT: "modified",
            RevisionChangeType.MERGED: "modified",
        }
        for change in changes:
            section = str(
                change.metadata.get("targetSectionCode")
                or change.metadata.get("baseSectionCode")
                or "UNMAPPED"
            )
            grouped[section][field_by_type[change.change_type]] += 1
        return [
            {"sectionKey": section, **counts}
            for section, counts in sorted(grouped.items())
        ]
