"""Conservative strong-negation mismatch signal."""

from __future__ import annotations

import re

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_TERMS: dict[str, tuple[str, ...]] = {
    "id": ("tidak", "bukan", "dilarang", "jangan", "tanpa"),
    "en": (
        "must not",
        "shall not",
        "prohibited",
        "without",
        "not",
        "no",
    ),
    "zh": ("不得", "禁止", "没有", "无需", "不", "无", "未"),
}


class NegationMismatchService:
    def check(
        self,
        source_text: str,
        target_text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> ConsistencyCheckResult:
        source = self.extract(source_text, source_language)
        target = self.extract(target_text, target_language)
        if not source and not target:
            status = ConsistencyStatus.NOT_APPLICABLE
        elif bool(source) == bool(target):
            status = ConsistencyStatus.MATCH
        else:
            status = ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH
        return ConsistencyCheckResult(
            status=status,
            source_values=source,
            target_values=target,
            details={
                "sourceHasStrongNegation": bool(source),
                "targetHasStrongNegation": bool(target),
                "ruleBasedSignalOnly": True,
            },
        )

    @staticmethod
    def extract(text: str, language: str) -> list[str]:
        folded = text.casefold()
        matches: list[tuple[int, str]] = []
        for term in _TERMS.get(language.casefold(), ()):
            if language.casefold() == "zh":
                matches.extend(
                    (match.start(), term)
                    for match in re.finditer(re.escape(term), text)
                )
            else:
                pattern = re.compile(
                    rf"(?<!\w){re.escape(term)}(?!\w)",
                    re.IGNORECASE,
                )
                matches.extend(
                    (match.start(), term)
                    for match in pattern.finditer(folded)
                )
        return [term for _, term in sorted(matches)]
