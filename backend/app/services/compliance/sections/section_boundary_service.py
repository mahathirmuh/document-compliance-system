"""Turn ordered canonical heading matches into source-bounded sections."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.schemas.compliance_internal import DetectedSectionData
from app.services.compliance._compat import int_value, read, string_value
from app.services.compliance.contracts import SectionMatch


class SectionBoundaryService:
    """Compute container-local boundaries without modifying source content."""

    def build(
        self,
        matches: Sequence[SectionMatch],
        blocks: Sequence[object],
        *,
        required_sections: Sequence[str] = (),
        allow_repeated_sections: bool = False,
    ) -> list[DetectedSectionData]:
        blocks_by_container: dict[object | None, list[object]] = defaultdict(list)
        for block in blocks:
            container_id = read(block, "container_id", None)
            blocks_by_container[container_id].append(block)
        for container_blocks in blocks_by_container.values():
            container_blocks.sort(
                key=lambda item: int_value(read(item, "block_order", 0)),
            )

        heading_groups = self._heading_groups(matches)
        filtered_groups: list[list[SectionMatch]] = []
        seen: set[str] = set()
        for group in heading_groups:
            primary = group[0]
            canonical = primary.canonical_code
            if (
                canonical in seen
                and not primary.is_repeatable
                and not allow_repeated_sections
            ):
                continue
            seen.add(canonical)
            filtered_groups.append(group)

        required = {item.upper() for item in required_sections}
        sections: list[DetectedSectionData] = []
        for index, group in enumerate(filtered_groups):
            primary = max(
                group,
                key=lambda item: (
                    item.confidence,
                    item.alias_priority,
                    -item.candidate.block_order,
                ),
            )
            candidate = primary.candidate
            container_blocks = blocks_by_container.get(
                candidate.container_id,
                [],
            )
            heading_end = max(
                item.candidate.block_order for item in group
            )
            next_heading_order = self._next_heading_order(
                filtered_groups,
                index,
                candidate.container_id,
            )
            content_blocks = [
                block
                for block in container_blocks
                if int_value(read(block, "block_order", 0)) > heading_end
                and (
                    next_heading_order is None
                    or int_value(read(block, "block_order", 0))
                    < next_heading_order
                )
            ]
            start_block = content_blocks[0] if content_blocks else None
            end_block = content_blocks[-1] if content_blocks else None
            start_order = (
                int_value(read(start_block, "block_order", heading_end + 1))
                if start_block is not None
                else heading_end + 1
            )
            if end_block is not None:
                end_order = int_value(read(end_block, "block_order", start_order))
            elif next_heading_order is not None:
                end_order = max(start_order - 1, next_heading_order - 1)
            else:
                end_order = start_order - 1

            heading_languages = tuple(
                dict.fromkeys(item.language_code for item in group)
            )
            heading_ids = tuple(
                item.candidate.block_id for item in group
            )
            sections.append(
                DetectedSectionData(
                    canonical_code=primary.canonical_code,
                    container_id=cast(UUID | None, candidate.container_id),
                    heading_block_id=cast(UUID | None, candidate.block_id),
                    heading_text=" / ".join(
                        item.candidate.text for item in group
                    ),
                    heading_language_code=(
                        primary.language_code
                        if len(heading_languages) == 1
                        else "mixed"
                    ),
                    match_type=primary.match_type,
                    match_confidence=min(
                        item.confidence for item in group
                    ),
                    section_order=len(sections) + 1,
                    start_block_order=start_order,
                    end_block_order=end_order,
                    start_block_id=cast(
                        UUID | None,
                        (
                            read(start_block, "id", None)
                            if start_block is not None
                            else None
                        ),
                    ),
                    end_block_id=cast(
                        UUID | None,
                        (
                            read(end_block, "id", None)
                            if end_block is not None
                            else None
                        ),
                    ),
                    source_reference=candidate.source_reference,
                    is_required=primary.canonical_code in required,
                    is_complete=bool(content_blocks),
                    metrics={
                        "headingLanguages": heading_languages,
                        "headingBlockIds": heading_ids,
                        "headingStartOrder": min(
                            item.candidate.block_order for item in group
                        ),
                        "headingEndOrder": heading_end,
                        "contentBlockCount": len(content_blocks),
                        "containerType": candidate.container_type,
                        "displayOrder": primary.display_order,
                        "repeatable": primary.is_repeatable,
                    },
                ),
            )
        return sections

    def detect_boundaries(
        self,
        matches: Sequence[SectionMatch],
        blocks: Sequence[object],
        *,
        required_sections: Sequence[str] = (),
        allow_repeated_sections: bool = False,
    ) -> list[DetectedSectionData]:
        return self.build(
            matches,
            blocks,
            required_sections=required_sections,
            allow_repeated_sections=allow_repeated_sections,
        )

    @staticmethod
    def _heading_groups(
        matches: Sequence[SectionMatch],
    ) -> list[list[SectionMatch]]:
        ordered = sorted(
            matches,
            key=lambda item: (
                item.candidate.container_index,
                item.candidate.block_order,
                item.canonical_code,
            ),
        )
        groups: list[list[SectionMatch]] = []
        for match in ordered:
            if not groups:
                groups.append([match])
                continue
            previous = groups[-1][-1]
            same_multilingual_heading = (
                previous.canonical_code == match.canonical_code
                and previous.candidate.container_id
                == match.candidate.container_id
                and 0
                < (
                    match.candidate.block_order
                    - previous.candidate.block_order
                )
                <= 2
                and previous.language_code != match.language_code
            )
            if same_multilingual_heading:
                groups[-1].append(match)
            else:
                groups.append([match])
        return groups

    @staticmethod
    def _next_heading_order(
        groups: Sequence[Sequence[SectionMatch]],
        current_index: int,
        container_id: object | None,
    ) -> int | None:
        for group in groups[current_index + 1 :]:
            candidate = group[0].candidate
            if candidate.container_id == container_id:
                return min(item.candidate.block_order for item in group)
        return None


def section_content_blocks(
    section: object,
    blocks: Sequence[object],
) -> list[object]:
    """Return blocks inside one detected section's inclusive boundaries."""

    container_id = read(section, "container_id", None)
    start = int_value(read(section, "start_block_order", 0))
    end = int_value(read(section, "end_block_order", -1))
    return [
        block
        for block in blocks
        if string_value(read(block, "container_id", ""))
        == string_value(container_id)
        and start <= int_value(read(block, "block_order", -1)) <= end
    ]
