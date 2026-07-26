"""Mandarin substring matching without whitespace assumptions."""

from __future__ import annotations

import re

from app.models.glossary_enums import GlossaryMatchType
from app.services.glossary.matching.exact_term_matcher import MatchSpan
from app.services.glossary.matching.term_normalizer import contains_han


class ChineseTermMatcher:
    """Match Han sequences and reject accidental Latin token fragments."""

    def find(
        self,
        text: str,
        term: str,
        *,
        case_sensitive: bool = False,
    ) -> list[MatchSpan]:
        if not text or not term:
            return []
        flags = 0 if case_sensitive else re.IGNORECASE
        spans: list[MatchSpan] = []
        term_has_han = contains_han(term)
        for match in re.finditer(re.escape(term), text, flags):
            start, end = match.span()
            before = text[start - 1] if start else ""
            after = text[end] if end < len(text) else ""
            if not term_has_han and (
                (before and before.isalnum())
                or (after and after.isalnum())
            ):
                continue
            if term_has_han and (
                (before and before.isascii() and before.isalnum())
                or (after and after.isascii() and after.isalnum())
            ):
                continue
            spans.append(
                MatchSpan(
                    start,
                    end,
                    GlossaryMatchType.CHINESE_SUBSTRING,
                )
            )
        return spans
