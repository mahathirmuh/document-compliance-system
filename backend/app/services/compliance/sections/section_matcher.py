"""Confidence-aware section alias matching in deterministic strategy order."""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    int_value,
    read,
    string_value,
)
from app.services.compliance.contracts import HeadingCandidate, SectionMatch
from app.services.compliance.sections.section_alias_service import (
    SectionAliasService,
    normalise_heading,
)

_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class SectionMatcher:
    """Map one heading candidate to the best active alias."""

    def __init__(
        self,
        *,
        minimum_confidence: float = 0.80,
        fuzzy_threshold: float = 0.88,
        regex_max_length: int = 500,
        regex_timeout_ms: int = 100,
    ) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between zero and one.")
        if not 0 <= fuzzy_threshold <= 1:
            raise ValueError("fuzzy_threshold must be between zero and one.")
        self.minimum_confidence = minimum_confidence
        self.fuzzy_threshold = fuzzy_threshold
        self.alias_service = SectionAliasService(
            regex_max_length=regex_max_length,
            regex_timeout_ms=regex_timeout_ms,
        )

    def match(
        self,
        heading: HeadingCandidate | str,
        aliases: Sequence[object],
        *,
        profile_id: object | None = None,
    ) -> SectionMatch | None:
        candidate = self._as_candidate(heading)
        normalized_heading = candidate.normalised_text
        active_aliases = self._active_aliases(aliases, profile_id)
        self.alias_service.validate_unique(active_aliases)

        possible: list[SectionMatch] = []
        for alias in active_aliases:
            result = self._evaluate(candidate, normalized_heading, alias)
            if (
                result is not None
                and result.confidence >= self.minimum_confidence
            ):
                possible.append(result)
        if not possible:
            return None
        return min(
            possible,
            key=lambda item: (
                self._strategy_rank(item.match_type),
                -item.confidence,
                -item.alias_priority,
                item.display_order,
                item.canonical_code,
                item.alias_text.casefold(),
            ),
        )

    def match_heading(
        self,
        heading: HeadingCandidate | str,
        aliases: Sequence[object],
        *,
        profile_id: object | None = None,
    ) -> SectionMatch | None:
        return self.match(heading, aliases, profile_id=profile_id)

    def match_all(
        self,
        candidates: Sequence[HeadingCandidate],
        aliases: Sequence[object],
        *,
        profile_id: object | None = None,
    ) -> list[SectionMatch]:
        matches = [
            match
            for candidate in candidates
            if (
                match := self.match(
                    candidate,
                    aliases,
                    profile_id=profile_id,
                )
            )
            is not None
        ]
        return sorted(
            matches,
            key=lambda item: (
                item.candidate.container_index,
                item.candidate.block_order,
                item.canonical_code,
            ),
        )

    def _evaluate(
        self,
        candidate: HeadingCandidate,
        normalized_heading: str,
        alias: object,
    ) -> SectionMatch | None:
        alias_text = string_value(read(alias, "alias_text", ""))
        raw_normalized = first(
            alias,
            "normalised_alias",
            "normalized_alias",
            default=None,
        )
        normalized_alias = (
            string_value(raw_normalized)
            if raw_normalized
            else normalise_heading(alias_text)
        )
        if not normalized_alias and not bool_value(
            read(alias, "is_regex", False),
        ):
            return None

        configured_type = enum_value(
            read(alias, "match_type", "EXACT"),
        ).upper()
        is_regex = bool_value(read(alias, "is_regex", False))
        actual_type: str | None = None
        confidence = 0.0

        if normalized_heading == normalized_alias and not is_regex:
            actual_type = "EXACT"
            confidence = 1.0
        elif configured_type == "PREFIX" and self._prefix_match(
            normalized_heading,
            normalized_alias,
        ):
            actual_type = "PREFIX"
            confidence = 0.95
        elif configured_type == "REGEX" or is_regex:
            pattern = self.alias_service.validate_regex(alias_text)
            if self.alias_service.regex_matches(
                pattern,
                normalized_heading[:200],
                candidate.text[:200],
            ):
                actual_type = "REGEX"
                confidence = min(
                    0.99,
                    max(
                        self.minimum_confidence,
                        float(
                            first(
                                alias,
                                "match_confidence",
                                "regex_confidence",
                                default=0.92,
                            ),
                        ),
                    ),
                )
        elif configured_type == "CONTAINS" and normalized_alias in (
            normalized_heading
        ):
            actual_type = "CONTAINS"
            confidence = 0.90
        elif (
            configured_type == "FUZZY"
            and not _HAN_RE.search(normalized_heading)
            and not _HAN_RE.search(normalized_alias)
        ):
            similarity = SequenceMatcher(
                None,
                normalized_heading,
                normalized_alias,
                autojunk=False,
            ).ratio()
            if similarity >= self.fuzzy_threshold:
                actual_type = "FUZZY"
                confidence = similarity

        if actual_type is None:
            return None
        alias_profile = first(
            alias,
            "profile_id",
            "section_alias_profile_id",
            default=None,
        )
        return SectionMatch(
            candidate=candidate,
            canonical_code=string_value(
                read(alias, "canonical_code", ""),
            ).upper(),
            language_code=enum_value(
                read(alias, "language_code", "any"),
                "any",
            ).casefold(),
            match_type=actual_type,
            confidence=round(confidence, 6),
            alias_text=alias_text,
            alias_priority=int_value(read(alias, "priority", 0)),
            display_order=int_value(read(alias, "display_order", 0)),
            is_repeatable=bool_value(
                read(alias, "is_repeatable", False),
            ),
            profile_id=(
                str(alias_profile) if alias_profile is not None else None
            ),
        )

    @staticmethod
    def _prefix_match(heading: str, alias: str) -> bool:
        if not heading.startswith(alias):
            return False
        if len(heading) == len(alias):
            return True
        if _HAN_RE.search(alias):
            return True
        return heading[len(alias)] in {" ", "-", "–", "—", "/", "("}

    @staticmethod
    def _strategy_rank(match_type: str) -> int:
        return {
            "EXACT": 0,
            "PREFIX": 1,
            "REGEX": 2,
            "CONTAINS": 3,
            "FUZZY": 4,
        }.get(match_type, 5)

    @staticmethod
    def _active_aliases(
        aliases: Sequence[object],
        profile_id: object | None,
    ) -> list[object]:
        requested_profile = (
            str(profile_id) if profile_id is not None else None
        )
        active: list[object] = []
        for alias in aliases:
            if not bool_value(read(alias, "is_active", True), True):
                continue
            alias_profile = first(
                alias,
                "profile_id",
                "section_alias_profile_id",
                default=None,
            )
            if (
                requested_profile is not None
                and alias_profile is not None
                and str(alias_profile) != requested_profile
            ):
                continue
            active.append(alias)
        return active

    @staticmethod
    def _as_candidate(heading: HeadingCandidate | str) -> HeadingCandidate:
        if isinstance(heading, HeadingCandidate):
            return heading
        text = str(heading)
        return HeadingCandidate(
            block=text,
            block_id=None,
            container_id=None,
            container_type="",
            container_index=0,
            block_order=0,
            source_reference="",
            text=text,
            normalised_text=normalise_heading(text),
            heading_level=None,
            candidate_score=1.0,
            reasons=("DIRECT_MATCH",),
        )
