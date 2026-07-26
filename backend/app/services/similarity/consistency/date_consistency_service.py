"""Conservative date normalization for Indonesian, English, and Chinese."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_MONTHS = {
    "january": 1,
    "januari": 1,
    "february": 2,
    "februari": 2,
    "march": 3,
    "maret": 3,
    "april": 4,
    "may": 5,
    "mei": 5,
    "june": 6,
    "juni": 6,
    "july": 7,
    "juli": 7,
    "august": 8,
    "agustus": 8,
    "september": 9,
    "october": 10,
    "oktober": 10,
    "november": 11,
    "december": 12,
    "desember": 12,
}
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_NAMED_RE = re.compile(
    rf"(?i)\b(?P<day>\d{{1,2}})\s+"
    rf"(?P<month>{_MONTH_PATTERN})\s+(?P<year>\d{{4}})\b"
)
_ISO_RE = re.compile(
    r"(?<!\d)(?P<year>\d{4})[-/.](?P<month>\d{1,2})[-/.]"
    r"(?P<day>\d{1,2})(?!\d)"
)
_DMY_RE = re.compile(
    r"(?<!\d)(?P<day>\d{1,2})[/.-](?P<month>\d{1,2})[/.-]"
    r"(?P<year>\d{4})(?!\d)"
)
_ZH_RE = re.compile(
    r"(?<!\d)(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*"
    r"(?P<day>\d{1,2})日?"
)


class DateConsistencyService:
    def check(
        self, source_text: str, target_text: str
    ) -> ConsistencyCheckResult:
        source, source_ambiguous, source_warnings = self.extract(source_text)
        target, target_ambiguous, target_warnings = self.extract(target_text)
        warnings = [*source_warnings, *target_warnings]
        if source_ambiguous or target_ambiguous:
            status = ConsistencyStatus.AMBIGUOUS
        elif not source and not target:
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
                "sourceAmbiguous": source_ambiguous,
                "targetAmbiguous": target_ambiguous,
            },
            warnings=warnings,
        )

    def extract(self, text: str) -> tuple[list[str], bool, list[str]]:
        matches: list[tuple[int, int, str]] = []
        ambiguous = False
        warnings: list[str] = []
        for regex, order in (
            (_ZH_RE, ("year", "month", "day")),
            (_ISO_RE, ("year", "month", "day")),
        ):
            for match in regex.finditer(text):
                normalized = self._date_value(
                    *(int(match.group(name)) for name in order)
                )
                if normalized:
                    matches.append((*match.span(), normalized))
        for match in _NAMED_RE.finditer(text):
            normalized = self._date_value(
                int(match.group("year")),
                _MONTHS[match.group("month").casefold()],
                int(match.group("day")),
            )
            if normalized:
                matches.append((*match.span(), normalized))
        occupied = [(start, end) for start, end, _ in matches]
        for match in _DMY_RE.finditer(text):
            if any(
                start <= match.start() and match.end() <= end
                for start, end in occupied
            ):
                continue
            day = int(match.group("day"))
            month = int(match.group("month"))
            if day <= 12 and month <= 12:
                ambiguous = True
                warnings.append(
                    f"AMBIGUOUS_DATE_FORMAT:{match.group(0)}"
                )
                continue
            normalized = self._date_value(
                int(match.group("year")), month, day
            )
            if normalized:
                matches.append((*match.span(), normalized))
        matches.sort(key=lambda item: item[0])
        return [value for _, _, value in matches], ambiguous, warnings

    @staticmethod
    def _date_value(year: int, month: int, day: int) -> str | None:
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
