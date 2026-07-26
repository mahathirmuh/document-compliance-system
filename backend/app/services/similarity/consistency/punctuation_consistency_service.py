"""Optional punctuation signal kept separate from legal consistency rules."""

from __future__ import annotations

from collections import Counter

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_SIGNIFICANT = ":;?!：；？！"


class PunctuationConsistencyService:
    def check(
        self, source_text: str, target_text: str
    ) -> ConsistencyCheckResult:
        source = [value for value in source_text if value in _SIGNIFICANT]
        target = [value for value in target_text if value in _SIGNIFICANT]
        if not source and not target:
            status = ConsistencyStatus.NOT_APPLICABLE
        elif sum(Counter(source).values()) == sum(Counter(target).values()):
            status = ConsistencyStatus.MATCH
        else:
            status = ConsistencyStatus.MISMATCH
        return ConsistencyCheckResult(
            status=status,
            source_values=source,
            target_values=target,
            details={"signalOnly": True},
        )
