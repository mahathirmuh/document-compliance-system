"""Compare finding evidence without resolving either historical finding."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from enum import StrEnum


class FindingComparisonStatus(StrEnum):
    NEW = "NEW"
    NO_LONGER_REPRODUCED = "NO_LONGER_REPRODUCED"
    REPEATED = "REPEATED"
    SEVERITY_INCREASED = "SEVERITY_INCREASED"
    SEVERITY_DECREASED = "SEVERITY_DECREASED"
    STATUS_CHANGED = "STATUS_CHANGED"
    UNCHANGED = "UNCHANGED"


_SEVERITY_RANK = {
    "INFORMATION": 0,
    "MINOR": 1,
    "MAJOR": 2,
    "CRITICAL": 3,
}


class RevisionFindingComparisonService:
    def compare(
        self,
        base_findings: Sequence[Mapping[str, object]],
        target_findings: Sequence[Mapping[str, object]],
    ) -> tuple[list[dict[str, object]], dict[str, int]]:
        base = self._indexed(base_findings)
        target = self._indexed(target_findings)
        results: list[dict[str, object]] = []
        counts: Counter[str] = Counter()
        for key in sorted(base.keys() | target.keys()):
            left = base.get(key)
            right = target.get(key)
            comparison_status = self._status(left, right)
            counts[comparison_status.value] += 1
            reference = right or left or {}
            results.append(
                {
                    "findingKey": key,
                    "findingCode": str(
                        reference.get("findingCode")
                        or reference.get("finding_code")
                        or "UNKNOWN"
                    ),
                    "comparisonStatus": comparison_status.value,
                    "baseSeverity": self._value(left, "severity"),
                    "targetSeverity": self._value(right, "severity"),
                    "baseStatus": self._value(left, "status"),
                    "targetStatus": self._value(right, "status"),
                    "section": self._value(reference, "section"),
                    "language": self._value(
                        reference, "language", "languageCode"
                    ),
                    "location": self._value(
                        reference, "location", "sourceReference"
                    ),
                    "candidateResolution": (
                        comparison_status
                        is FindingComparisonStatus.NO_LONGER_REPRODUCED
                    ),
                }
            )
        return results, dict(counts)

    @classmethod
    def _indexed(
        cls, findings: Sequence[Mapping[str, object]]
    ) -> dict[str, Mapping[str, object]]:
        """Retain duplicate findings instead of silently overwriting them."""

        grouped: defaultdict[
            str, list[Mapping[str, object]]
        ] = defaultdict(list)
        for finding in findings:
            grouped[cls._key(finding)].append(finding)
        indexed: dict[str, Mapping[str, object]] = {}
        for key in sorted(grouped):
            for occurrence, finding in enumerate(grouped[key], start=1):
                indexed[
                    key if occurrence == 1 else f"{key}#{occurrence}"
                ] = finding
        return indexed

    @staticmethod
    def _key(item: Mapping[str, object]) -> str:
        explicit = item.get("deduplicationKey") or item.get(
            "deduplication_key"
        )
        if explicit:
            return str(explicit)
        parts = (
            item.get("findingCode") or item.get("finding_code") or "UNKNOWN",
            item.get("section") or item.get("detected_section_id") or "",
            item.get("languageCode") or item.get("language_code") or "",
            item.get("sourceReference") or item.get("source_reference") or "",
        )
        return "|".join(str(part) for part in parts)

    def _status(
        self,
        left: Mapping[str, object] | None,
        right: Mapping[str, object] | None,
    ) -> FindingComparisonStatus:
        if left is None:
            return FindingComparisonStatus.NEW
        if right is None:
            return FindingComparisonStatus.NO_LONGER_REPRODUCED
        left_severity = str(left.get("severity") or "").upper()
        right_severity = str(right.get("severity") or "").upper()
        if _SEVERITY_RANK.get(right_severity, 0) > _SEVERITY_RANK.get(
            left_severity, 0
        ):
            return FindingComparisonStatus.SEVERITY_INCREASED
        if _SEVERITY_RANK.get(right_severity, 0) < _SEVERITY_RANK.get(
            left_severity, 0
        ):
            return FindingComparisonStatus.SEVERITY_DECREASED
        if str(left.get("status")) != str(right.get("status")):
            return FindingComparisonStatus.STATUS_CHANGED
        if self._comparable_values(left) == self._comparable_values(right):
            return FindingComparisonStatus.UNCHANGED
        return FindingComparisonStatus.REPEATED

    @staticmethod
    def _comparable_values(
        item: Mapping[str, object]
    ) -> tuple[str, ...]:
        """Compare business evidence, excluding per-run finding identifiers."""

        values = (
            item.get("findingCode") or item.get("finding_code"),
            item.get("severity"),
            item.get("status"),
            item.get("section") or item.get("detected_section_id"),
            item.get("languageCode") or item.get("language_code"),
            item.get("location")
            or item.get("sourceReference")
            or item.get("source_reference"),
        )
        return tuple(str(value or "") for value in values)

    @staticmethod
    def _value(
        item: Mapping[str, object] | None, *keys: str
    ) -> str | None:
        if item is None:
            return None
        for key in keys:
            value = item.get(key)
            if value is not None:
                return str(value)
        return None
