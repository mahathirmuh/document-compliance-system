"""Canonical multi-signal alignment for two retained revisions."""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import UUID

_SPACE_RE = re.compile(r"\s+")


def normalize_revision_text(value: str) -> str:
    """Normalize only for matching; original text remains untouched."""

    return _SPACE_RE.sub(" ", value.strip().casefold())


@dataclass(frozen=True, slots=True)
class CanonicalRevisionItem:
    """One bounded canonical entity from extraction/compliance provenance."""

    id: UUID
    text: str
    order: int
    entity_type: str = "PARAGRAPH"
    language_code: str | None = None
    source_reference: str | None = None
    container_id: UUID | None = None
    container_identity: str | None = None
    section_id: UUID | None = None
    section_code: str | None = None
    translation_group_id: UUID | None = None
    translation_group_type: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def normalized_text(self) -> str:
        return normalize_revision_text(self.text)


@dataclass(frozen=True, slots=True)
class AlignedRevisionPair:
    base: CanonicalRevisionItem | None
    target: CanonicalRevisionItem | None
    text_similarity: float
    structural_similarity: float
    alignment_confidence: float
    moved: bool = False
    alignment_signals: tuple[str, ...] = ()


@dataclass(slots=True)
class _TargetAlignmentIndex:
    """Bounded candidate indexes that avoid quadratic block scans."""

    by_reference: dict[tuple[object, ...], list[tuple[int, int]]]
    by_text: dict[tuple[object, ...], list[tuple[int, int]]]
    by_structure: dict[tuple[object, ...], list[tuple[int, int]]]
    by_section: dict[tuple[object, ...], list[tuple[int, int]]]
    by_entity: dict[tuple[object, ...], list[tuple[int, int]]]


class RevisionAlignmentService:
    """Align using canonical structure, exact/fuzzy text, and position."""

    def __init__(
        self,
        *,
        fuzzy_threshold: float = 0.58,
        moved_position_tolerance: int = 2,
        maximum_candidates_per_signal: int = 64,
    ) -> None:
        if not 0 <= fuzzy_threshold <= 1:
            raise ValueError("fuzzy_threshold must be between zero and one.")
        self.fuzzy_threshold = fuzzy_threshold
        self.moved_position_tolerance = moved_position_tolerance
        if maximum_candidates_per_signal < 1:
            raise ValueError(
                "maximum_candidates_per_signal must be positive."
            )
        self.maximum_candidates_per_signal = (
            maximum_candidates_per_signal
        )

    def align(
        self,
        base_items: list[CanonicalRevisionItem],
        target_items: list[CanonicalRevisionItem],
    ) -> list[AlignedRevisionPair]:
        """Return one-to-one alignments plus explicit additions/removals."""

        remaining_targets = set(range(len(target_items)))
        aligned: list[AlignedRevisionPair] = []
        target_index = self._build_index(target_items)

        # Exact source references inside the same canonical structure are the
        # strongest stable Phase 6/8 provenance signal.
        for base in base_items:
            candidate = self._best_candidate(
                base,
                target_items,
                self._candidate_indices(
                    base,
                    target_index,
                    remaining_targets,
                ),
            )
            if candidate is None:
                aligned.append(
                    AlignedRevisionPair(
                        base=base,
                        target=None,
                        text_similarity=0.0,
                        structural_similarity=0.0,
                        alignment_confidence=1.0,
                        alignment_signals=("REMOVED",),
                    )
                )
                continue
            target_index, score, text_score, structural, signals = candidate
            remaining_targets.remove(target_index)
            target = target_items[target_index]
            moved = self._is_moved(base, target, text_score)
            aligned.append(
                AlignedRevisionPair(
                    base=base,
                    target=target,
                    text_similarity=text_score,
                    structural_similarity=structural,
                    alignment_confidence=score,
                    moved=moved,
                    alignment_signals=tuple(signals),
                )
            )

        for target_index in sorted(remaining_targets):
            aligned.append(
                AlignedRevisionPair(
                    base=None,
                    target=target_items[target_index],
                    text_similarity=0.0,
                    structural_similarity=0.0,
                    alignment_confidence=1.0,
                    alignment_signals=("ADDED",),
                )
            )
        return aligned

    def _best_candidate(
        self,
        base: CanonicalRevisionItem,
        targets: list[CanonicalRevisionItem],
        candidates: set[int],
    ) -> tuple[int, float, float, float, list[str]] | None:
        best: tuple[int, float, float, float, list[str]] | None = None
        for index in sorted(
            candidates,
            key=lambda item: (
                targets[item].order,
                str(targets[item].id),
            ),
        ):
            target = targets[index]
            if base.entity_type != target.entity_type:
                continue
            text_score = SequenceMatcher(
                None, base.normalized_text, target.normalized_text
            ).ratio()
            structural, signals = self._structural_score(base, target)
            position_distance = abs(base.order - target.order)
            position_score = 1.0 / (1.0 + position_distance)

            exact_text = bool(base.normalized_text) and (
                base.normalized_text == target.normalized_text
            )
            exact_reference = bool(base.source_reference) and (
                base.source_reference == target.source_reference
            )
            same_section = base.section_code == target.section_code
            if exact_text:
                score = max(0.92, 0.70 * text_score + 0.30 * structural)
                signals.append("NORMALIZED_EXACT_TEXT")
            elif exact_reference and same_section:
                score = max(
                    0.72,
                    0.45 * text_score + 0.45 * structural + 0.10,
                )
                signals.append("SOURCE_REFERENCE")
            else:
                score = (
                    0.62 * text_score
                    + 0.28 * structural
                    + 0.10 * position_score
                )
            if score < self.fuzzy_threshold:
                continue
            if best is None or score > best[1]:
                best = (index, min(score, 1.0), text_score, structural, signals)
        return best

    def _candidate_indices(
        self,
        base: CanonicalRevisionItem,
        index: _TargetAlignmentIndex,
        remaining: set[int],
    ) -> set[int]:
        keys_and_indexes = (
            (
                index.by_reference,
                (
                    base.entity_type,
                    base.source_reference,
                    base.section_code,
                ),
                base.source_reference is not None,
            ),
            (
                index.by_text,
                (base.entity_type, base.normalized_text),
                bool(base.normalized_text),
            ),
            (
                index.by_structure,
                self._structure_key(base),
                True,
            ),
            (
                index.by_section,
                (base.entity_type, base.section_code),
                base.section_code is not None,
            ),
            (
                index.by_entity,
                (base.entity_type,),
                True,
            ),
        )
        candidates: set[int] = set()
        for lookup, key, enabled in keys_and_indexes:
            if not enabled:
                continue
            candidates.update(
                self._nearest_available(
                    lookup.get(key, []),
                    order=base.order,
                    remaining=remaining,
                )
            )
        return candidates

    def _nearest_available(
        self,
        ordered: list[tuple[int, int]],
        *,
        order: int,
        remaining: set[int],
    ) -> list[int]:
        """Return nearby still-unmatched indexes with bounded outward scan."""

        if not ordered:
            return []
        center = bisect_left(ordered, (order, -1))
        left = center - 1
        right = center
        output: list[int] = []
        # Matched indexes may remain in a bucket. Bound inspection separately
        # so highly duplicated text cannot reintroduce an unbounded scan.
        inspection_limit = self.maximum_candidates_per_signal * 8
        inspected = 0
        while (
            len(output) < self.maximum_candidates_per_signal
            and inspected < inspection_limit
            and (left >= 0 or right < len(ordered))
        ):
            choose_left = right >= len(ordered) or (
                left >= 0
                and abs(ordered[left][0] - order)
                <= abs(ordered[right][0] - order)
            )
            pair = ordered[left] if choose_left else ordered[right]
            if choose_left:
                left -= 1
            else:
                right += 1
            inspected += 1
            if pair[1] in remaining:
                output.append(pair[1])
        return output

    @classmethod
    def _build_index(
        cls, targets: list[CanonicalRevisionItem]
    ) -> _TargetAlignmentIndex:
        by_reference: defaultdict[
            tuple[object, ...], list[tuple[int, int]]
        ] = defaultdict(list)
        by_text: defaultdict[
            tuple[object, ...], list[tuple[int, int]]
        ] = defaultdict(list)
        by_structure: defaultdict[
            tuple[object, ...], list[tuple[int, int]]
        ] = defaultdict(list)
        by_section: defaultdict[
            tuple[object, ...], list[tuple[int, int]]
        ] = defaultdict(list)
        by_entity: defaultdict[
            tuple[object, ...], list[tuple[int, int]]
        ] = defaultdict(list)
        for item_index, item in enumerate(targets):
            ordered_index = (item.order, item_index)
            if item.source_reference is not None:
                by_reference[
                    (
                        item.entity_type,
                        item.source_reference,
                        item.section_code,
                    )
                ].append(ordered_index)
            if item.normalized_text:
                by_text[
                    (item.entity_type, item.normalized_text)
                ].append(ordered_index)
            by_structure[cls._structure_key(item)].append(ordered_index)
            if item.section_code is not None:
                by_section[
                    (item.entity_type, item.section_code)
                ].append(ordered_index)
            by_entity[(item.entity_type,)].append(ordered_index)
        mappings = (
            by_reference,
            by_text,
            by_structure,
            by_section,
            by_entity,
        )
        for mapping in mappings:
            for values in mapping.values():
                values.sort()
        return _TargetAlignmentIndex(
            by_reference=dict(by_reference),
            by_text=dict(by_text),
            by_structure=dict(by_structure),
            by_section=dict(by_section),
            by_entity=dict(by_entity),
        )

    @staticmethod
    def _structure_key(
        item: CanonicalRevisionItem,
    ) -> tuple[object, ...]:
        return (
            item.entity_type,
            item.section_code,
            item.translation_group_type,
            item.container_identity,
            item.language_code,
        )

    @staticmethod
    def _structural_score(
        base: CanonicalRevisionItem,
        target: CanonicalRevisionItem,
    ) -> tuple[float, list[str]]:
        signals: list[str] = []
        weighted = 0.0
        possible = 0.0
        comparisons = (
            ("CANONICAL_SECTION", base.section_code, target.section_code, 0.30),
            (
                "TRANSLATION_GROUP_TYPE",
                base.translation_group_type,
                target.translation_group_type,
                0.20,
            ),
            (
                "CONTAINER_IDENTITY",
                base.container_identity,
                target.container_identity,
                0.20,
            ),
            (
                "LANGUAGE",
                base.language_code,
                target.language_code,
                0.15,
            ),
            (
                "SOURCE_REFERENCE",
                base.source_reference,
                target.source_reference,
                0.15,
            ),
        )
        for label, left, right, weight in comparisons:
            if left is None or right is None:
                continue
            possible += weight
            if left == right:
                weighted += weight
                signals.append(label)
        if possible == 0:
            return 0.5, signals
        return weighted / possible, signals

    def _is_moved(
        self,
        base: CanonicalRevisionItem,
        target: CanonicalRevisionItem,
        text_similarity: float,
    ) -> bool:
        if text_similarity < 0.94:
            return False
        return (
            base.section_code != target.section_code
            or base.container_identity != target.container_identity
            or abs(base.order - target.order) > self.moved_position_tolerance
        )
