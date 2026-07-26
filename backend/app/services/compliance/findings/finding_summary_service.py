"""Finding counts used by score, status, reports, and exports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.services.compliance._compat import (
    bool_value,
    enum_value,
    read,
)

_OPEN_STATUSES = {"OPEN", "IN_REVIEW", "REOPENED"}


class FindingSummaryService:
    def summarize(self, findings: Sequence[object]) -> dict[str, object]:
        severities: Counter[str] = Counter()
        statuses: Counter[str] = Counter()
        system_generated = 0
        manual = 0
        for finding in findings:
            severities[
                enum_value(read(finding, "severity", "INFORMATION")).upper()
            ] += 1
            statuses[
                enum_value(read(finding, "status", "OPEN")).upper()
            ] += 1
            if bool_value(
                read(finding, "is_system_generated", True),
                True,
            ):
                system_generated += 1
            else:
                manual += 1
        open_count = sum(statuses[status] for status in _OPEN_STATUSES)
        return {
            "total": len(findings),
            "critical": severities["CRITICAL"],
            "major": severities["MAJOR"],
            "minor": severities["MINOR"],
            "information": severities["INFORMATION"],
            "open": open_count,
            "systemGenerated": system_generated,
            "manual": manual,
            "byStatus": dict(sorted(statuses.items())),
            "bySeverity": dict(sorted(severities.items())),
        }

    @staticmethod
    def open_findings(findings: Sequence[object]) -> list[object]:
        return [
            finding
            for finding in findings
            if enum_value(read(finding, "status", "OPEN")).upper()
            in _OPEN_STATUSES
        ]

