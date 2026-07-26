"""Page-local positional grouping for PDF text blocks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.schemas.compliance_internal import TranslationGroupData
from app.services.compliance._compat import (
    enum_value,
    first,
    float_value,
    int_value,
    language_code,
    mapping,
    read,
)
from app.services.compliance.constants import GROUP_TYPE_PDF_POSITIONAL
from app.services.compliance.grouping._group_builder import (
    build_group,
    container_id_for,
    member_from_block,
    source_reference_for,
)


class PositionalGroupingService:
    """Group aligned adjacent PDF blocks using only extraction coordinates."""

    def __init__(
        self,
        *,
        maximum_vertical_gap: float = 120.0,
        maximum_block_distance: int = 3,
    ) -> None:
        if maximum_vertical_gap < 0:
            raise ValueError("maximum_vertical_gap must be non-negative.")
        if maximum_block_distance < 1:
            raise ValueError("maximum_block_distance must be positive.")
        self.maximum_vertical_gap = maximum_vertical_gap
        self.maximum_block_distance = maximum_block_distance

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
        by_page: dict[tuple[object | None, int], list[object]] = defaultdict(list)
        for block in blocks:
            block_type = enum_value(
                read(block, "block_type", ""),
            ).upper()
            if block_type in {"HEADER", "FOOTER", "PAGE_NUMBER"}:
                continue
            page = self._page_number(block)
            by_page[(container_id_for(block), page)].append(block)

        groups: list[TranslationGroupData] = []
        for (container_id, page), page_blocks in sorted(
            by_page.items(),
            key=lambda item: (item[0][1], str(item[0][0] or "")),
        ):
            ordered = sorted(page_blocks, key=self._position_key)
            current: list[object] = []
            for block in ordered:
                code = language_code(block)
                if code not in target:
                    continue
                if current and not self._is_adjacent(current[-1], block):
                    self._flush(
                        current,
                        groups,
                        expected=expected,
                        container_id=container_id,
                        page=page,
                        group_index=start_index + len(groups),
                        include_singletons=include_singletons,
                    )
                    current = []
                if code in {language_code(item) for item in current}:
                    self._flush(
                        current,
                        groups,
                        expected=expected,
                        container_id=container_id,
                        page=page,
                        group_index=start_index + len(groups),
                        include_singletons=include_singletons,
                    )
                    current = []
                current.append(block)
                if len({language_code(item) for item in current}) >= len(
                    expected,
                ):
                    self._flush(
                        current,
                        groups,
                        expected=expected,
                        container_id=container_id,
                        page=page,
                        group_index=start_index + len(groups),
                        include_singletons=include_singletons,
                    )
                    current = []
            self._flush(
                current,
                groups,
                expected=expected,
                container_id=container_id,
                page=page,
                group_index=start_index + len(groups),
                include_singletons=include_singletons,
            )
        return groups

    def group_pdf_blocks(
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

    def _flush(
        self,
        blocks: Sequence[object],
        groups: list[TranslationGroupData],
        *,
        expected: Sequence[str],
        container_id: object | None,
        page: int,
        group_index: int,
        include_singletons: bool,
    ) -> None:
        if not blocks or (len(blocks) == 1 and not include_singletons):
            return
        members = [member_from_block(block) for block in blocks]
        gaps = [
            max(0.0, self._y(blocks[index + 1]) - self._bottom(blocks[index]))
            for index in range(len(blocks) - 1)
        ]
        x_values = [self._x(block) for block in blocks]
        x_spread = max(x_values) - min(x_values) if x_values else 0.0
        detected_ratio = len(
            {member.language_code for member in members},
        ) / max(1, len(expected))
        average_gap = sum(gaps) / len(gaps) if gaps else 0.0
        gap_quality = max(
            0.0,
            1.0 - average_gap / max(1.0, self.maximum_vertical_gap),
        )
        alignment_quality = max(0.0, 1.0 - x_spread / 200.0)
        confidence = (
            0.30
            + 0.45 * detected_ratio
            + 0.15 * gap_quality
            + 0.10 * alignment_quality
        )
        bbox = self._group_bbox(blocks)
        groups.append(
            build_group(
                members,
                group_index=group_index,
                group_type=GROUP_TYPE_PDF_POSITIONAL,
                expected_languages=expected,
                container_id=container_id,
                source_reference=source_reference_for(
                    blocks,
                    fallback=f"PDF:page={page}:group={group_index}",
                ),
                confidence=confidence,
                metrics={
                    "strategy": "PDF_POSITIONAL",
                    "pageNumber": page,
                    "averageVerticalGap": round(average_gap, 6),
                    "xSpread": round(x_spread, 6),
                    "bbox": bbox,
                    "semanticSimilarityEvaluated": False,
                },
            ),
        )

    def _is_adjacent(self, previous: object, current: object) -> bool:
        order_distance = abs(
            int_value(read(current, "block_order", 0))
            - int_value(read(previous, "block_order", 0))
        )
        if order_distance > self.maximum_block_distance:
            return False
        vertical_gap = self._y(current) - self._bottom(previous)
        if vertical_gap < -10:
            return False
        if vertical_gap > self.maximum_vertical_gap:
            return False
        previous_width = max(1.0, self._width(previous))
        current_width = max(1.0, self._width(current))
        width_ratio = min(previous_width, current_width) / max(
            previous_width,
            current_width,
        )
        x_difference = abs(self._x(current) - self._x(previous))
        return x_difference <= max(80.0, previous_width * 0.35) or (
            width_ratio >= 0.55 and x_difference <= 160.0
        )

    @staticmethod
    def _location(block: object) -> dict[str, object]:
        return mapping(
            first(block, "location", "location_json", default={}),
        )

    @classmethod
    def _bbox(cls, block: object) -> tuple[float, float, float, float]:
        location = cls._location(block)
        raw_bbox = read(location, "bbox", None)
        if isinstance(raw_bbox, Sequence) and not isinstance(
            raw_bbox,
            (str, bytes, bytearray),
        ):
            values = list(raw_bbox)
            if len(values) == 4:
                return tuple(float_value(item) for item in values)  # type: ignore[return-value]
        x = float_value(read(location, "x", 0))
        y = float_value(read(location, "y", 0))
        width = float_value(read(location, "width", 0))
        height = float_value(read(location, "height", 0))
        return (x, y, x + width, y + height)

    @classmethod
    def _x(cls, block: object) -> float:
        return cls._bbox(block)[0]

    @classmethod
    def _y(cls, block: object) -> float:
        return cls._bbox(block)[1]

    @classmethod
    def _bottom(cls, block: object) -> float:
        return cls._bbox(block)[3]

    @classmethod
    def _width(cls, block: object) -> float:
        bbox = cls._bbox(block)
        return max(0.0, bbox[2] - bbox[0])

    @classmethod
    def _position_key(cls, block: object) -> tuple[float, float, int]:
        return (
            cls._y(block),
            cls._x(block),
            int_value(read(block, "block_order", 0)),
        )

    @classmethod
    def _group_bbox(
        cls,
        blocks: Sequence[object],
    ) -> tuple[float, float, float, float]:
        boxes = [cls._bbox(block) for block in blocks]
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    @classmethod
    def _page_number(cls, block: object) -> int:
        direct = read(block, "page_number", None)
        if direct is not None:
            return int_value(direct, 1)
        location = cls._location(block)
        return int_value(first(location, "page", "pageNumber", default=1), 1)
