"""Whole-word matching for Indonesian and English terms."""

from __future__ import annotations

import re

from app.models.glossary_enums import GlossaryMatchType
from app.services.glossary.matching.exact_term_matcher import MatchSpan


class WholeWordMatcher:
    """Use Unicode word boundaries for non-Mandarin glossary forms."""

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
        pattern = rf"(?<![\w]){re.escape(term)}(?![\w])"
        return [
            MatchSpan(
                match.start(),
                match.end(),
                GlossaryMatchType.WHOLE_WORD,
            )
            for match in re.finditer(pattern, text, flags)
        ]
