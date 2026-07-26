"""Classify aligned revision entities without editing either source."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import UUID

from app.models.revision_change import (
    REVISION_TEXT_SNAPSHOT_MAX_CHARACTERS,
    RevisionChangeType,
    RevisionEntityType,
)
from app.services.revision_comparison.revision_alignment_service import (
    AlignedRevisionPair,
    CanonicalRevisionItem,
)


@dataclass(frozen=True, slots=True)
class DetectedRevisionChange:
    change_type: RevisionChangeType
    entity_type: RevisionEntityType
    base_id: UUID | None
    target_id: UUID | None
    base_text_snapshot: str | None
    target_text_snapshot: str | None
    language_code: str | None
    source_reference_base: str | None
    source_reference_target: str | None
    text_similarity: float
    structural_similarity: float
    alignment_confidence: float
    character_change_count: int
    word_change_count: int
    metadata: dict[str, object] = field(default_factory=dict)


class RevisionChangeDetectionService:
    """Added/removed/modified/moved/unchanged are always supported."""

    def __init__(
        self,
        *,
        unchanged_threshold: float = 0.999,
        snapshot_max_characters: int = REVISION_TEXT_SNAPSHOT_MAX_CHARACTERS,
    ) -> None:
        self.unchanged_threshold = unchanged_threshold
        self.snapshot_max_characters = max(100, snapshot_max_characters)

    def detect(
        self, pairs: list[AlignedRevisionPair]
    ) -> list[DetectedRevisionChange]:
        return [self.classify(pair) for pair in pairs]

    def classify(
        self, pair: AlignedRevisionPair
    ) -> DetectedRevisionChange:
        base = pair.base
        target = pair.target
        if base is None:
            assert target is not None
            change_type = RevisionChangeType.ADDED
        elif target is None:
            change_type = RevisionChangeType.REMOVED
        elif pair.moved:
            change_type = RevisionChangeType.MOVED
        elif pair.text_similarity >= self.unchanged_threshold and (
            base.metadata == target.metadata
        ):
            change_type = RevisionChangeType.UNCHANGED
        else:
            change_type = RevisionChangeType.MODIFIED

        base_text = base.text if base else ""
        target_text = target.text if target else ""
        character_changes = self._edit_count(base_text, target_text)
        word_changes = self._edit_count(
            base_text.split(), target_text.split()
        )
        reference = target or base
        assert reference is not None
        return DetectedRevisionChange(
            change_type=change_type,
            entity_type=self._entity_type(reference),
            base_id=base.id if base else None,
            target_id=target.id if target else None,
            base_text_snapshot=(
                base_text[: self.snapshot_max_characters] if base else None
            ),
            target_text_snapshot=(
                target_text[: self.snapshot_max_characters]
                if target
                else None
            ),
            language_code=(
                reference.language_code
            ),
            source_reference_base=(
                base.source_reference if base else None
            ),
            source_reference_target=(
                target.source_reference if target else None
            ),
            text_similarity=pair.text_similarity,
            structural_similarity=pair.structural_similarity,
            alignment_confidence=pair.alignment_confidence,
            character_change_count=character_changes,
            word_change_count=word_changes,
            metadata={
                "alignmentSignals": list(pair.alignment_signals),
                "baseOrder": base.order if base else None,
                "targetOrder": target.order if target else None,
                "baseSectionCode": base.section_code if base else None,
                "targetSectionCode": target.section_code if target else None,
            },
        )

    @staticmethod
    def _edit_count(
        left: Sequence[object],
        right: Sequence[object],
    ) -> int:
        matcher = SequenceMatcher(None, left, right)
        count = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                count += max(i2 - i1, j2 - j1)
        return count

    @staticmethod
    def _entity_type(item: CanonicalRevisionItem) -> RevisionEntityType:
        value = item.entity_type.upper()
        aliases = {
            "TEXT": RevisionEntityType.PARAGRAPH,
            "CELL": RevisionEntityType.XLSX_CELL,
            "MERGED_CELL": RevisionEntityType.XLSX_CELL,
            "WORKSHEET_TITLE": RevisionEntityType.HEADING,
        }
        if value in aliases:
            return aliases[value]
        try:
            return RevisionEntityType(value)
        except ValueError:
            return RevisionEntityType.PARAGRAPH
