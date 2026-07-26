"""Literal glossary matcher."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.glossary_enums import GlossaryMatchType


@dataclass(frozen=True, slots=True)
class MatchSpan:
    start: int
    end: int
    match_type: GlossaryMatchType


class ExactTermMatcher:
    """Find literal terms while preserving source offsets."""

    def find(
        self,
        text: str,
        term: str,
        *,
        case_sensitive: bool,
    ) -> list[MatchSpan]:
        if not text or not term:
            return []
        flags = 0 if case_sensitive else re.IGNORECASE
        match_type = (
            GlossaryMatchType.CASE_SENSITIVE
            if case_sensitive
            else GlossaryMatchType.EXACT
        )
        return [
            MatchSpan(match.start(), match.end(), match_type)
            for match in re.finditer(re.escape(term), text, flags)
        ]
