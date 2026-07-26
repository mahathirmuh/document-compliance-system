"""Deterministic finding fingerprints, in-run deduplication, and repeat links."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, cast

from app.services.compliance._compat import (
    bool_value,
    copy_update,
    enum_value,
    first,
    json_safe,
    mapping,
    read,
    string_value,
)

_SEVERITY_RANK = {
    "CRITICAL": 4,
    "MAJOR": 3,
    "MINOR": 2,
    "INFORMATION": 1,
}


class FindingDeduplicationService:
    """Preserve audit history while linking equivalent findings across runs."""

    def fingerprint(self, finding: object) -> str:
        metrics = mapping(
            first(
                finding,
                "metrics",
                "metrics_json",
                default={},
            )
        )
        explicit = first(
            finding,
            "deduplication_key",
            default=first(
                metrics,
                "deduplication_key",
                default=None,
            ),
        )
        if explicit:
            return str(explicit)
        expected_value = mapping(
            first(
                finding,
                "expected_value",
                "expected_value_json",
                default={},
            )
        )
        payload = {
            "findingCode": enum_value(read(finding, "finding_code", "")),
            "documentRevisionId": string_value(
                read(finding, "document_revision_id", ""),
            ),
            "sourceReference": string_value(
                read(finding, "source_reference", ""),
            ),
            "languageCode": enum_value(
                read(finding, "language_code", ""),
            ),
            "section": string_value(
                first(
                    finding,
                    "detected_section_code",
                    "section_code",
                    default=first(
                        metrics,
                        "detected_section_code",
                        default=first(
                            expected_value,
                            "canonical_section",
                            default=read(
                                finding,
                                "detected_section_id",
                                "",
                            ),
                        ),
                    ),
                ),
            ),
            "translationGroupSignature": string_value(
                first(
                    finding,
                    "translation_group_signature",
                    default=first(
                        metrics,
                        "groupSignature",
                        "translationGroupSignature",
                        default="",
                    ),
                ),
            ),
        }
        if not bool_value(read(finding, "is_system_generated", True), True):
            payload["manualTitle"] = string_value(
                read(finding, "title", ""),
            ).casefold()
        canonical = json.dumps(
            json_safe(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def deduplicate(self, findings: Sequence[object]) -> list[object]:
        retained: dict[str, object] = {}
        positions: dict[str, int] = {}
        for position, finding in enumerate(findings):
            fingerprint = self.fingerprint(finding)
            existing = retained.get(fingerprint)
            if existing is None:
                retained[fingerprint] = copy_update(
                    finding,
                    deduplication_key=fingerprint,
                )
                positions[fingerprint] = position
                continue
            retained[fingerprint] = self._merge(existing, finding, fingerprint)
        return [
            retained[fingerprint]
            for fingerprint, _ in sorted(
                positions.items(),
                key=lambda item: item[1],
            )
        ]

    def link_repeated(
        self,
        current_findings: Sequence[object],
        previous_findings: Sequence[object],
    ) -> list[object]:
        previous_by_fingerprint = {
            self.fingerprint(finding): finding
            for finding in previous_findings
            if bool_value(
                read(finding, "is_system_generated", True),
                True,
            )
        }
        linked: list[object] = []
        for finding in current_findings:
            if not bool_value(
                read(finding, "is_system_generated", True),
                True,
            ):
                linked.append(finding)
                continue
            fingerprint = self.fingerprint(finding)
            previous = previous_by_fingerprint.get(fingerprint)
            if previous is None:
                linked.append(
                    copy_update(
                        finding,
                        deduplication_key=fingerprint,
                    ),
                )
                continue
            previous_id = read(previous, "id", None)
            linked.append(
                copy_update(
                    finding,
                    deduplication_key=fingerprint,
                    is_repeat=True,
                    previous_finding_id=(
                        previous_id if previous_id is not None else None
                    ),
                ),
            )
        return linked

    def merge_revalidation(
        self,
        current_system_findings: Sequence[object],
        previous_findings: Sequence[object],
    ) -> list[object]:
        """Link repeats and retain all manual findings unchanged."""

        linked = self.link_repeated(
            self.deduplicate(current_system_findings),
            previous_findings,
        )
        manual = [
            finding
            for finding in previous_findings
            if not bool_value(
                read(finding, "is_system_generated", True),
                True,
            )
        ]
        return [*linked, *manual]

    def compare(
        self,
        current_findings: Sequence[object],
        previous_findings: Sequence[object],
    ) -> tuple[list[object], list[object], list[object]]:
        current = {
            self.fingerprint(finding): finding for finding in current_findings
        }
        previous = {
            self.fingerprint(finding): finding for finding in previous_findings
        }
        new = [current[key] for key in sorted(current.keys() - previous.keys())]
        not_reproduced = [
            previous[key] for key in sorted(previous.keys() - current.keys())
        ]
        repeated = [
            current[key] for key in sorted(current.keys() & previous.keys())
        ]
        return new, not_reproduced, repeated

    @staticmethod
    def _merge(
        existing: object,
        duplicate: object,
        fingerprint: str,
    ) -> object:
        existing_metrics = mapping(read(existing, "metrics", {}))
        duplicate_metrics = mapping(read(duplicate, "metrics", {}))
        occurrence_count = (
            int(cast(Any, existing_metrics.get("occurrenceCount", 1))) + 1
        )
        references = {
            string_value(read(existing, "source_reference", "")),
            string_value(read(duplicate, "source_reference", "")),
        }
        references.discard("")
        merged_metrics = {
            **duplicate_metrics,
            **existing_metrics,
            "occurrenceCount": occurrence_count,
            "duplicateSourceReferences": tuple(sorted(references)),
        }
        existing_severity = enum_value(
            read(existing, "severity", "INFORMATION"),
        ).upper()
        duplicate_severity = enum_value(
            read(duplicate, "severity", "INFORMATION"),
        ).upper()
        severity = max(
            (existing_severity, duplicate_severity),
            key=lambda item: _SEVERITY_RANK.get(item, 0),
        )
        return copy_update(
            existing,
            severity=severity,
            metrics=merged_metrics,
            deduplication_key=fingerprint,
        )
