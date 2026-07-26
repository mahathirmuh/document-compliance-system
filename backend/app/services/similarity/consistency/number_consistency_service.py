"""Locale-aware numeric consistency without unsafe semantic conversion."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_NUMBER_RE = re.compile(
    r"(?<!\d)(?<![A-Za-z_])[-+]?"
    r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?:\s*(?:%|‰|percent|persen|百分之))?",
    re.IGNORECASE,
)
_REFERENCE_PREFIX_RE = re.compile(
    r"(?i)\b(?:section|bagian|table|tabel|figure|gambar|appendix|lampiran)"
    r"\s+(?P<number>\d+(?:\.\d+)*)"
)


class NumberConsistencyService:
    def check(
        self,
        source_text: str,
        target_text: str,
        *,
        ignore_heading_references: bool = True,
    ) -> ConsistencyCheckResult:
        source = self.extract(
            source_text,
            ignore_heading_references=ignore_heading_references,
        )
        target = self.extract(
            target_text,
            ignore_heading_references=ignore_heading_references,
        )
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

    def extract(
        self,
        text: str,
        *,
        ignore_heading_references: bool = True,
    ) -> list[str]:
        ignored_spans = (
            [match.span("number") for match in _REFERENCE_PREFIX_RE.finditer(text)]
            if ignore_heading_references
            else []
        )
        output: list[str] = []
        for match in _NUMBER_RE.finditer(text):
            if any(
                start <= match.start() and match.end() <= end
                for start, end in ignored_spans
            ):
                continue
            normalized = self._normalize(match.group(0))
            if normalized is not None:
                output.append(normalized)
        return output

    @staticmethod
    def _normalize(raw: str) -> str | None:
        folded = raw.strip().casefold()
        percent = bool(
            re.search(r"(?:%|‰|percent|persen|百分之)\s*$", folded)
        )
        per_mille = "‰" in folded
        numeric = re.sub(
            r"\s*(?:%|‰|percent|persen|百分之)\s*$",
            "",
            folded,
        ).replace(" ", "")
        if "," in numeric and "." in numeric:
            if numeric.rfind(",") > numeric.rfind("."):
                numeric = numeric.replace(".", "").replace(",", ".")
            else:
                numeric = numeric.replace(",", "")
        elif numeric.count(",") == 1:
            left, right = numeric.split(",")
            numeric = (
                left + right
                if len(right) == 3 and len(left.lstrip("+-")) <= 3
                else left + "." + right
            )
        elif numeric.count(".") > 1:
            numeric = numeric.replace(".", "")
        elif numeric.count(".") == 1:
            left, right = numeric.split(".")
            if len(right) == 3 and len(left.lstrip("+-")) <= 3:
                numeric = left + right
        try:
            value = Decimal(numeric).normalize()
        except InvalidOperation:
            return None
        suffix = "‰" if per_mille else ("%" if percent else "")
        return f"{format(value, 'f')}{suffix}"
