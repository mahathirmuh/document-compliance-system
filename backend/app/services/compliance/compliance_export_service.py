"""Export-safe JSON primitives and tabular rows for API adapters."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from app.services.compliance._compat import (
    enum_value,
    first,
    json_safe,
    read,
    sequence,
    string_value,
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ABSOLUTE_WINDOWS_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_WINDOWS_PATH_ANYWHERE_RE = re.compile(r"(?:^|[^A-Za-z0-9])[a-zA-Z]:[\\/]")
_UNIX_PATH_VALUE_RE = re.compile(r"""(?:^|[=;,\s"'])/(?:[^/\s]|$)""")
_SAFE_SOURCE_PREFIXES = ("PDF:", "DOCX:", "XLSX:", "OCR:")
_SCORE_COMPONENTS = (
    ("document_code", "documentCode"),
    ("language_presence", "languagePresence"),
    ("language_coverage", "languageCoverage"),
    ("section_completeness", "sectionCompleteness"),
    ("language_order", "languageOrder"),
    ("translation_groups", "translationGroups"),
    ("table_completeness", "tableCompleteness"),
)


def spreadsheet_safe_value(
    value: object,
    *,
    maximum_characters: int = 32_767,
) -> object:
    """Neutralize spreadsheet formulas while preserving non-string types."""

    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = _CONTROL_RE.sub("", str(value))[:maximum_characters]
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def safe_source_reference(value: object) -> str:
    reference = _CONTROL_RE.sub("", string_value(value))[:1000]
    upper = reference.upper()
    prefix = next(
        (
            candidate
            for candidate in _SAFE_SOURCE_PREFIXES
            if upper.startswith(candidate)
        ),
        None,
    )
    suffix = reference[len(prefix) :].lstrip() if prefix is not None else ""
    if (
        _ABSOLUTE_WINDOWS_PATH_RE.match(reference)
        or _WINDOWS_PATH_ANYWHERE_RE.search(reference)
        or reference.startswith(("/", "\\\\"))
        or reference.casefold().startswith("file://")
        or suffix.startswith(("/", "\\\\"))
        or _UNIX_PATH_VALUE_RE.search(reference)
        or (prefix is not None and ("/" in suffix or "\\" in suffix))
        or (prefix is None and ("/" in reference or "\\" in reference))
    ):
        return "[redacted source reference]"
    if prefix is not None:
        return reference
    return reference


class ComplianceExportService:
    """Build bounded payloads; authorization/scope stays in the API layer."""

    def __init__(self, *, maximum_rows: int = 200_000) -> None:
        if maximum_rows < 1:
            raise ValueError("maximum_rows must be positive.")
        self.maximum_rows = maximum_rows

    def json_payload(
        self,
        run: object,
        *,
        score_breakdown: object | None = None,
        languages: object | None = None,
        sections: Sequence[object] = (),
        translation_groups: Sequence[object] = (),
        findings: Sequence[object] = (),
    ) -> dict[str, object]:
        return {
            "summary": self._safe_mapping(run),
            "scoreBreakdown": self._safe_value(score_breakdown),
            "languages": self._safe_value(languages),
            "sections": self._safe_value(sections),
            "translationGroups": self._safe_value(translation_groups),
            "findings": self._safe_value(findings),
            "limitations": {
                "semanticSimilarityEvaluated": False,
                "translationMeaningValidated": False,
            },
        }

    build_json_payload = json_payload

    def workbook_data(
        self,
        run: object,
        *,
        score_breakdown: object | None = None,
        languages: object | None = None,
        sections: Sequence[object] = (),
        translation_groups: Sequence[object] = (),
        findings: Sequence[object] = (),
    ) -> dict[str, list[dict[str, object]]]:
        sheets = {
            "Summary": [self._summary_row(run)],
            "Score Breakdown": self._score_rows(score_breakdown),
            "Languages": self._generic_rows(languages),
            "Sections": self._generic_rows(sections),
            "Translation Groups": self._generic_rows(translation_groups),
            "Findings": [
                self._tabular_mapping(self._safe_finding(finding))
                for finding in findings
            ],
        }
        for sheet_name, rows in sheets.items():
            if len(rows) > self.maximum_rows:
                raise ValueError(
                    f"{sheet_name} exceeds the configured export row limit.",
                )
        return sheets

    build_workbook_data = workbook_data

    def finding_rows(
        self,
        findings: Sequence[object],
    ) -> list[dict[str, object]]:
        if len(findings) > self.maximum_rows:
            raise ValueError("Finding export exceeds the configured row limit.")
        return [
            self._tabular_mapping(self._safe_finding(finding)) for finding in findings
        ]

    @staticmethod
    def _safe_finding(finding: object) -> dict[str, object]:
        return ComplianceExportService._safe_mapping(finding)

    @staticmethod
    def _safe_value(value: object) -> object:
        return _sanitize_source_references(json_safe(value))

    @staticmethod
    def _safe_mapping(value: object) -> dict[str, object]:
        safe = ComplianceExportService._safe_value(value)
        if not isinstance(safe, Mapping):
            return {"value": safe}
        return {str(key): item for key, item in safe.items()}

    @staticmethod
    def _summary_row(run: object) -> dict[str, object]:
        data = ComplianceExportService._safe_mapping(run)
        document = read(data, "document", {})
        revision = read(data, "revision", {})
        validation_rule = read(data, "validation_rule", {})
        rule_snapshot = read(data, "rule_snapshot", {})
        document_code = first(
            document,
            "base_document_code",
            default=first(
                revision,
                "full_document_code",
                default="",
            ),
        )
        rule_code = first(
            rule_snapshot,
            "rule_code",
            "code",
            default=first(validation_rule, "code", default=""),
        )
        values = (
            ("Document Code", document_code),
            ("Revision", first(revision, "revision_code", default="")),
            ("Validation Rule", rule_code),
            (
                "Compliance Status",
                first(data, "compliance_status", default=""),
            ),
            (
                "Compliance Score",
                first(data, "compliance_score", default=0),
            ),
            (
                "Validated At",
                first(data, "completed_at", "created_at", default=""),
            ),
            (
                "Required Languages",
                first(data, "required_languages", default=[]),
            ),
            (
                "Missing Languages",
                first(data, "missing_languages", default=[]),
            ),
            (
                "Required Sections",
                first(data, "required_sections", default=[]),
            ),
            (
                "Missing Sections",
                first(data, "missing_sections", default=[]),
            ),
            ("Total Findings", first(data, "total_findings", default=0)),
        )
        return {
            header: spreadsheet_safe_value(ComplianceExportService._flatten(value))
            for header, value in values
        }

    @staticmethod
    def _tabular_mapping(value: object) -> dict[str, object]:
        data = ComplianceExportService._safe_mapping(value)
        return {
            key: spreadsheet_safe_value(
                ComplianceExportService._flatten(item),
            )
            for key, item in data.items()
        }

    @staticmethod
    def _flatten(value: object) -> object:
        safe = json_safe(value)
        if isinstance(safe, (dict, list)):
            import json

            return json.dumps(
                safe,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        return safe

    @staticmethod
    def _generic_rows(value: object) -> list[dict[str, object]]:
        if value is None:
            return []
        safe = ComplianceExportService._safe_value(value)
        if isinstance(safe, Mapping):
            return [
                {
                    "key": spreadsheet_safe_value(key),
                    "value": spreadsheet_safe_value(
                        ComplianceExportService._flatten(item),
                    ),
                }
                for key, item in safe.items()
            ]
        return [
            ComplianceExportService._tabular_mapping(item) for item in sequence(safe)
        ]

    @staticmethod
    def _score_rows(
        score_breakdown: object | None,
    ) -> list[dict[str, object]]:
        if score_breakdown is None:
            return []
        rows: list[dict[str, object]] = []
        for field_name, public_name in _SCORE_COMPONENTS:
            result = read(score_breakdown, field_name, None)
            if result is None:
                continue
            rows.append(
                {
                    "validator": public_name,
                    "earned": read(result, "earned", 0),
                    "maximum": read(result, "maximum", 0),
                    "status": enum_value(read(result, "status", "")),
                },
            )
        validators = read(score_breakdown, "validators", {})
        if not rows and isinstance(validators, Mapping):
            for validator, result in validators.items():
                result_mapping = result if isinstance(result, Mapping) else {}
                rows.append(
                    {
                        "validator": spreadsheet_safe_value(validator),
                        "earned": read(result_mapping, "earned", 0),
                        "maximum": read(result_mapping, "maximum", 0),
                        "status": enum_value(
                            read(result_mapping, "status", ""),
                        ),
                    },
                )
        rows.append(
            {
                "validator": "FINAL",
                "earned": first(
                    score_breakdown,
                    "final_score",
                    "finalScore",
                    default=0,
                ),
                "maximum": first(
                    score_breakdown,
                    "maximum_score",
                    "maximumScore",
                    default=100,
                ),
                "status": "",
            },
        )
        return rows


def _sanitize_source_references(value: object) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            text_key = str(key)
            normalized_key = text_key.replace("_", "").replace("-", "").casefold()
            sanitized[text_key] = (
                safe_source_reference(item)
                if normalized_key == "sourcereference"
                else _sanitize_source_references(item)
            )
        return sanitized
    if isinstance(value, list):
        return [_sanitize_source_references(item) for item in value]
    return value
