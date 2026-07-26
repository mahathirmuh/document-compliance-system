"""Adjacent-paragraph structural grouping for DOCX content."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.schemas.compliance_internal import TranslationGroupData
from app.services.compliance._compat import (
    enum_value,
    int_value,
    language_code,
    read,
    string_value,
)
from app.services.compliance.constants import (
    GROUP_TYPE_HEADING,
    GROUP_TYPE_PARAGRAPH,
)
from app.services.compliance.grouping._group_builder import (
    build_group,
    container_id_for,
    member_from_block,
    source_reference_for,
)

_ELIGIBLE_TYPES = {"TEXT", "PARAGRAPH", "HEADER", "FOOTER"}
_BOUNDARY_TYPES = {
    "HEADING",
    "TABLE",
    "TABLE_ROW",
    "TABLE_CELL",
    "CELL",
    "MERGED_CELL",
}


class ParagraphGroupingService:
    """Group adjacent language runs without making semantic comparisons."""

    def __init__(
        self,
        *,
        maximum_block_distance: int = 3,
        maximum_group_gap: int = 1,
    ) -> None:
        if maximum_block_distance < 1:
            raise ValueError("maximum_block_distance must be positive.")
        if maximum_group_gap < 0:
            raise ValueError("maximum_group_gap must be non-negative.")
        self.maximum_block_distance = maximum_block_distance
        self.maximum_group_gap = maximum_group_gap

    def group(
        self,
        blocks: Sequence[object],
        expected_languages: Sequence[str],
        *,
        start_index: int = 0,
        include_singletons: bool = True,
    ) -> list[TranslationGroupData]:
        expected = tuple(language.casefold() for language in expected_languages)
        target = set(expected)
        by_container: dict[object | None, list[object]] = defaultdict(list)
        for block in blocks:
            by_container[container_id_for(block)].append(block)

        groups: list[TranslationGroupData] = []
        for container_id, container_blocks in sorted(
            by_container.items(),
            key=lambda item: (
                int_value(read(item[1][0], "container_index", 0))
                if item[1]
                else 0,
                str(item[0] or ""),
            ),
        ):
            ordered = sorted(
                container_blocks,
                key=lambda block: int_value(
                    read(block, "block_order", 0),
                ),
            )
            heading_run: list[object] = []

            def flush_headings(
                active_container_id: object | None = container_id,
            ) -> None:
                nonlocal heading_run
                if len(heading_run) > 1:
                    groups.append(
                        self._build(
                            heading_run,
                            expected,
                            active_container_id,
                            start_index + len(groups),
                        ),
                    )
                heading_run = []

            for block in ordered:
                block_type = enum_value(
                    read(block, "block_type", ""),
                ).upper()
                if block_type != "HEADING":
                    flush_headings()
                    continue
                code = language_code(block)
                if code not in target:
                    flush_headings()
                    continue
                if heading_run and (
                    code in {language_code(item) for item in heading_run}
                    or int_value(read(block, "block_order", 0))
                    - int_value(read(heading_run[-1], "block_order", 0))
                    > self.maximum_block_distance
                ):
                    flush_headings()
                heading_run.append(block)
                if len({language_code(item) for item in heading_run}) >= len(
                    expected,
                ):
                    flush_headings()
            flush_headings()

            current: list[object] = []
            ignored_gap = 0
            previous_order: int | None = None

            def flush(active_container_id: object | None = container_id) -> None:
                nonlocal current, ignored_gap, previous_order
                if current and (include_singletons or len(current) > 1):
                    group = self._build(
                        current,
                        expected,
                        active_container_id,
                        start_index + len(groups),
                    )
                    groups.append(group)
                current = []
                ignored_gap = 0
                previous_order = None

            for block in ordered:
                block_type = enum_value(
                    read(block, "block_type", ""),
                ).upper()
                if block_type in _BOUNDARY_TYPES:
                    flush()
                    continue
                if block_type and block_type not in _ELIGIBLE_TYPES:
                    continue
                current_order = int_value(read(block, "block_order", 0))
                code = language_code(block)
                if code not in target:
                    if current:
                        ignored_gap += 1
                        if ignored_gap > self.maximum_group_gap:
                            flush()
                    continue
                if (
                    current
                    and previous_order is not None
                    and current_order - previous_order
                    > self.maximum_block_distance
                ):
                    flush()
                current_languages = {
                    language_code(item) for item in current
                }
                if code in current_languages:
                    flush()
                current.append(block)
                previous_order = current_order
                ignored_gap = 0
                if len(current_languages | {code}) >= len(expected):
                    flush()
            flush()
        return groups

    def group_paragraphs(
        self,
        blocks: Sequence[object],
        expected_languages: Sequence[str],
        *,
        start_index: int = 0,
    ) -> list[TranslationGroupData]:
        return self.group(
            blocks,
            expected_languages,
            start_index=start_index,
        )

    @staticmethod
    def _build(
        blocks: Sequence[object],
        expected: Sequence[str],
        container_id: object | None,
        group_index: int,
    ) -> TranslationGroupData:
        members = [member_from_block(block) for block in blocks]
        detected_ratio = len(
            {member.language_code for member in members},
        ) / max(1, len(expected))
        orders = [
            int_value(read(block, "block_order", 0)) for block in blocks
        ]
        distance = max(orders) - min(orders) if len(orders) > 1 else 0
        adjacency = 1.0 / (1.0 + max(0, distance - len(blocks) + 1))
        lengths = [
            max(1, len(string_value(read(block, "text", ""))))
            for block in blocks
        ]
        length_ratio = min(lengths) / max(lengths)
        confidence = (
            0.35
            + 0.45 * detected_ratio
            + 0.10 * adjacency
            + 0.10 * length_ratio
        )
        group_type = (
            GROUP_TYPE_HEADING
            if all(
                enum_value(read(block, "block_type", "")).upper()
                == "HEADING"
                for block in blocks
            )
            else GROUP_TYPE_PARAGRAPH
        )
        return build_group(
            members,
            group_index=group_index,
            group_type=group_type,
            expected_languages=expected,
            container_id=container_id,
            source_reference=source_reference_for(
                blocks,
                fallback=f"DOCX:group={group_index}",
            ),
            confidence=confidence,
            metrics={
                "strategy": "ADJACENT_PARAGRAPHS",
                "blockDistance": distance,
                "lengthRatio": round(length_ratio, 6),
                "semanticSimilarityEvaluated": False,
            },
        )
