"""Cross-language section/table/figure/appendix identifier checks."""

from __future__ import annotations

import re
from collections import Counter

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "section",
        re.compile(
            r"(?i)(?:\bsection\b|\bbagian\b|第)\s*"
            r"(?P<id>\d+(?:\.\d+)*)(?:\s*节)?"
        ),
    ),
    (
        "table",
        re.compile(
            r"(?i)(?:\btable\b|\btabel\b|表)\s*(?P<id>[A-Z]?\d+)"
        ),
    ),
    (
        "figure",
        re.compile(
            r"(?i)(?:\bfigure\b|\bgambar\b|图)\s*(?P<id>[A-Z]?\d+)"
        ),
    ),
    (
        "appendix",
        re.compile(
            r"(?i)(?:\bappendix\b|\blampiran\b|附录)\s*(?P<id>[A-Z0-9]+)"
        ),
    ),
)


class ReferenceConsistencyService:
    def check(
        self, source_text: str, target_text: str
    ) -> ConsistencyCheckResult:
        source = self.extract(source_text)
        target = self.extract(target_text)
        if not source and not target:
            status = ConsistencyStatus.NOT_APPLICABLE
        elif Counter(source) == Counter(target):
            status = ConsistencyStatus.MATCH
        else:
            status = ConsistencyStatus.MISMATCH
        return ConsistencyCheckResult(
            status=status,
            source_values=source,
            target_values=target,
            details={
                "missingInTarget": list((Counter(source) - Counter(target)).elements()),
                "unexpectedInTarget": list(
                    (Counter(target) - Counter(source)).elements()
                ),
            },
        )

    @staticmethod
    def extract(text: str) -> list[str]:
        values: list[tuple[int, str]] = []
        for kind, pattern in _PATTERNS:
            values.extend(
                (match.start(), f"{kind}:{match.group('id').upper()}")
                for match in pattern.finditer(text)
            )
        return [value for _, value in sorted(values)]
