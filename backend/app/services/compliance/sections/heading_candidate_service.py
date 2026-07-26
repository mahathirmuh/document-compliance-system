"""Detect plausible headings across PDF, DOCX, and XLSX extracted blocks."""

from __future__ import annotations

import re
from collections.abc import Sequence
from statistics import median

from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    float_value,
    int_value,
    mapping,
    read,
    string_value,
)
from app.services.compliance.contracts import HeadingCandidate
from app.services.compliance.sections.section_alias_service import (
    has_numbering_prefix,
    normalise_heading,
)

_UPPERCASE_LETTER_RE = re.compile(r"[A-ZÀ-ÖØ-Þ]")
_LOWERCASE_LETTER_RE = re.compile(r"[a-zà-öø-ÿ]")
_HEADING_STYLE_RE = re.compile(
    r"^(?:heading|title|judul|header)\s*\d*$",
    re.IGNORECASE,
)


class HeadingCandidateService:
    """Score cheap structural signals; alias matching remains a later step."""

    def __init__(
        self,
        *,
        maximum_characters: int = 200,
        minimum_score: float = 0.5,
    ) -> None:
        if maximum_characters < 1:
            raise ValueError("maximum_characters must be positive.")
        if not 0 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between zero and one.")
        self.maximum_characters = maximum_characters
        self.minimum_score = minimum_score

    def detect(
        self,
        blocks: Sequence[object],
        *,
        alias_texts: Sequence[str] = (),
    ) -> list[HeadingCandidate]:
        font_baseline = self._font_baseline(blocks)
        normalised_aliases = {
            normalise_heading(alias)
            for alias in alias_texts
            if normalise_heading(alias)
        }
        candidates: list[HeadingCandidate] = []
        for block in blocks:
            candidate = self._candidate(
                block,
                font_baseline=font_baseline,
                normalised_aliases=normalised_aliases,
            )
            if candidate is not None:
                candidates.append(candidate)
        return sorted(
            candidates,
            key=lambda item: (
                item.container_index,
                item.block_order,
                item.source_reference,
            ),
        )

    def find_candidates(
        self,
        blocks: Sequence[object],
        *,
        alias_texts: Sequence[str] = (),
    ) -> list[HeadingCandidate]:
        """Compatibility alias for callers that prefer an explicit verb."""

        return self.detect(blocks, alias_texts=alias_texts)

    def is_candidate(
        self,
        block: object,
        *,
        alias_texts: Sequence[str] = (),
    ) -> bool:
        return bool(self.detect([block], alias_texts=alias_texts))

    def _candidate(
        self,
        block: object,
        *,
        font_baseline: float | None,
        normalised_aliases: set[str],
    ) -> HeadingCandidate | None:
        text = string_value(first(block, "text", "normalised_text", default=""))
        normalized = normalise_heading(text)
        if not normalized or len(normalized) > self.maximum_characters:
            return None

        block_type = enum_value(read(block, "block_type", "")).upper()
        style_name = string_value(read(block, "style_name", ""))
        heading_level_raw = read(block, "heading_level", None)
        heading_level = (
            int_value(heading_level_raw)
            if heading_level_raw is not None
            else None
        )
        metadata = mapping(
            first(block, "metadata", "metadata_json", default={}),
        )
        location = mapping(
            first(block, "location", "location_json", default={}),
        )
        score = 0.0
        reasons: list[str] = []

        if block_type in {"HEADING", "WORKSHEET_TITLE"}:
            score += 0.75
            reasons.append("EXPLICIT_HEADING_TYPE")
        if heading_level is not None:
            score += 0.25
            reasons.append("HEADING_LEVEL")
        if style_name and _HEADING_STYLE_RE.match(style_name.strip()):
            score += 0.55
            reasons.append("DOCX_HEADING_STYLE")
        if has_numbering_prefix(text):
            score += 0.25
            reasons.append("NUMBERED")
        if self._is_short_uppercase(text):
            score += 0.30
            reasons.append("SHORT_UPPERCASE")

        font_size = float_value(
            first(
                metadata,
                "font_size",
                "fontSize",
                default=first(location, "font_size", "fontSize", default=0.0),
            ),
        )
        if (
            font_baseline is not None
            and font_size > 0
            and font_size >= font_baseline * 1.15
        ):
            score += 0.35
            reasons.append("RELATIVE_FONT_SIZE")
        if bool_value(first(metadata, "bold", "isBold", default=False)):
            score += 0.25
            reasons.append("BOLD")
        if bool_value(first(metadata, "isMerged", "is_merged", default=False)):
            score += 0.20
            reasons.append("MERGED_CELL")
        row = int_value(
            first(
                location,
                "row",
                default=first(metadata, "row", default=0),
            ),
        )
        if (
            block_type in {"CELL", "MERGED_CELL", "WORKSHEET_TITLE"}
            and row in {0, 1}
        ):
            score += 0.20
            reasons.append("XLSX_TOP_ROW")
        if normalized in normalised_aliases:
            score += 0.75
            reasons.append("KNOWN_ALIAS")

        final_score = min(1.0, score)
        if final_score < self.minimum_score:
            return None
        container_id = first(block, "container_id", default=None)
        return HeadingCandidate(
            block=block,
            block_id=read(block, "id", None),
            container_id=container_id,
            container_type=enum_value(
                read(block, "container_type", ""),
            ).upper(),
            container_index=int_value(read(block, "container_index", 0)),
            block_order=int_value(read(block, "block_order", 0)),
            source_reference=string_value(
                read(block, "source_reference", ""),
            ),
            text=text,
            normalised_text=normalized,
            heading_level=heading_level,
            candidate_score=final_score,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _font_baseline(blocks: Sequence[object]) -> float | None:
        sizes: list[float] = []
        for block in blocks:
            metadata = mapping(
                first(block, "metadata", "metadata_json", default={}),
            )
            location = mapping(
                first(block, "location", "location_json", default={}),
            )
            size = float_value(
                first(
                    metadata,
                    "font_size",
                    "fontSize",
                    default=first(
                        location,
                        "font_size",
                        "fontSize",
                        default=0,
                    ),
                ),
            )
            if size > 0:
                sizes.append(size)
        return median(sizes) if sizes else None

    @staticmethod
    def _is_short_uppercase(text: str) -> bool:
        stripped = text.strip()
        if not stripped or len(stripped) > 100:
            return False
        has_upper = _UPPERCASE_LETTER_RE.search(stripped) is not None
        has_lower = _LOWERCASE_LETTER_RE.search(stripped) is not None
        return has_upper and not has_lower
