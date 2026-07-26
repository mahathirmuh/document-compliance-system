"""Conservative prefix/inflection matching for ID and EN."""

from __future__ import annotations

import re

from app.models.glossary_enums import GlossaryMatchType
from app.services.glossary.matching.exact_term_matcher import MatchSpan


class InflectionMatcher:
    """Match a configured term plus a bounded word suffix."""

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
        pattern = rf"(?<![\w]){re.escape(term)}[\w-]{{0,32}}(?![\w])"
        return [
            MatchSpan(
                match.start(),
                match.end(),
                GlossaryMatchType.INFLECTION,
            )
            for match in re.finditer(pattern, text, flags)
        ]
