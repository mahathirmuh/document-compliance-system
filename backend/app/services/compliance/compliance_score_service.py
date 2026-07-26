"""Weighted compliance score, finding penalties, and critical cap."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from app.services.compliance._compat import (
    enum_value,
    first,
    float_value,
    mapping,
    option,
    read,
)
from app.services.compliance.constants import DEFAULT_WEIGHTS
from app.services.compliance.contracts import ScoreBreakdown

_OPEN_STATUSES = {"OPEN", "IN_REVIEW", "REOPENED"}
_WEIGHT_FIELD_NAMES: dict[str, tuple[str, ...]] = {
    "document_code": ("document_code_weight", "documentCode"),
    "language_presence": (
        "language_presence_weight",
        "languagePresence",
    ),
    "language_coverage": (
        "language_coverage_weight",
        "languageCoverage",
    ),
    "section_completeness": (
        "section_completeness_weight",
        "sectionCompleteness",
    ),
    "language_order": ("language_order_weight", "languageOrder"),
    "translation_group": (
        "translation_group_weight",
        "translationGroups",
        "translationGroup",
    ),
    "table_completeness": (
        "table_completeness_weight",
        "tableCompleteness",
        "tables",
    ),
}


class ComplianceWeightError(ValueError):
    code = "COMPLIANCE_RULE_INVALID"


class ComplianceScoreService:
    """Calculate once from immutable validator results; never touches the DB."""

    def validate_weights(self, rule_or_weights: object | None) -> dict[str, float]:
        weights = self.resolve_weights(rule_or_weights)
        for name, weight in weights.items():
            if not math.isfinite(weight) or weight < 0:
                raise ComplianceWeightError(
                    f"Weight {name!r} must be a finite non-negative number.",
                )
        total = sum(weights.values())
        if not math.isclose(total, 100.0, abs_tol=0.001):
            raise ComplianceWeightError(
                f"Compliance validator weights must total 100, got {total:g}.",
            )
        return weights

    def resolve_weights(
        self,
        rule_or_weights: object | None,
    ) -> dict[str, float]:
        if rule_or_weights is None:
            return dict(DEFAULT_WEIGHTS)
        supplied = mapping(rule_or_weights)
        nested = mapping(
            first(
                rule_or_weights,
                "weights",
                "weights_json",
                default=supplied.get("weights", {}),
            ),
        )
        resolved: dict[str, float] = {}
        for canonical, names in _WEIGHT_FIELD_NAMES.items():
            value: object | None = None
            for name in names:
                value = read(rule_or_weights, name, None)
                if value is None:
                    value = read(nested, name, None)
                if value is not None:
                    break
            resolved[canonical] = float_value(
                value,
                DEFAULT_WEIGHTS[canonical],
            )
        return resolved

    def calculate(
        self,
        validator_results: Sequence[object],
        findings: Sequence[object] = (),
        rule: object | None = None,
        *,
        validate_rule_weights: bool = True,
    ) -> ScoreBreakdown:
        weights = (
            self.validate_weights(rule)
            if validate_rule_weights
            else self.resolve_weights(rule)
        )
        result_breakdown: dict[str, dict[str, object]] = {}
        weighted_score = 0.0
        maximum_score = 0.0
        for result in validator_results:
            code = enum_value(
                first(
                    result,
                    "validator_code",
                    "code",
                    default="UNKNOWN",
                ),
            ).upper()
            earned = float_value(
                first(result, "score", "earned_score", default=0.0),
            )
            maximum = float_value(
                first(
                    result,
                    "maximum_score",
                    "maximum",
                    "weight",
                    default=0.0,
                ),
            )
            if not math.isfinite(earned) or not math.isfinite(maximum):
                raise ValueError("Validator scores must be finite.")
            maximum = max(0.0, maximum)
            earned = min(maximum, max(0.0, earned))
            result_breakdown[code] = {
                "earned": round(earned, 4),
                "maximum": round(maximum, 4),
                "status": enum_value(read(result, "status", "")),
            }
            weighted_score += earned
            maximum_score += maximum

        # A caller may omit disabled/non-scoring validators, but configured
        # weights remain the authoritative maximum for the final 0-100 score.
        configured_maximum = sum(weights.values())
        if maximum_score > configured_maximum + 0.001:
            raise ComplianceWeightError(
                "Validator maximum scores exceed the configured 100-point "
                f"budget ({maximum_score:g}).",
            )
        maximum_score = max(maximum_score, configured_maximum)
        counts = self._open_severity_counts(findings)
        major_penalty_value = float_value(
            option(rule or {}, "major_finding_penalty", 5.0),
            5.0,
        )
        minor_penalty_value = float_value(
            option(rule or {}, "minor_finding_penalty", 1.0),
            1.0,
        )
        major_penalty = counts["MAJOR"] * max(0.0, major_penalty_value)
        minor_penalty = counts["MINOR"] * max(0.0, minor_penalty_value)
        total_penalty = major_penalty + minor_penalty
        score_before_cap = max(0.0, weighted_score - total_penalty)
        score_cap: float | None = None
        final_score = score_before_cap
        if counts["CRITICAL"] > 0:
            configured_cap = option(
                rule or {},
                "critical_finding_score_cap",
                69.0,
            )
            if configured_cap is not None:
                score_cap = max(0.0, min(100.0, float_value(configured_cap)))
                final_score = min(final_score, score_cap)
        final_score = round(max(0.0, min(100.0, final_score)), 4)
        return ScoreBreakdown(
            weighted_score=round(weighted_score, 4),
            major_penalty=round(major_penalty, 4),
            minor_penalty=round(minor_penalty, 4),
            total_penalty=round(total_penalty, 4),
            score_before_cap=round(score_before_cap, 4),
            score_cap=score_cap,
            final_score=final_score,
            maximum_score=round(maximum_score, 4),
            validators=result_breakdown,
            finding_counts={
                severity.casefold(): counts[severity]
                for severity in (
                    "CRITICAL",
                    "MAJOR",
                    "MINOR",
                    "INFORMATION",
                )
            },
        )

    def calculate_score(
        self,
        validator_results: Sequence[object],
        findings: Sequence[object] = (),
        rule: object | None = None,
    ) -> ScoreBreakdown:
        return self.calculate(validator_results, findings, rule)

    @staticmethod
    def _open_severity_counts(
        findings: Sequence[object],
    ) -> Counter[str]:
        counts: Counter[str] = Counter()
        for finding in findings:
            status = enum_value(read(finding, "status", "OPEN")).upper()
            if status not in _OPEN_STATUSES:
                continue
            severity = enum_value(
                read(finding, "severity", "INFORMATION"),
            ).upper()
            counts[severity] += 1
        return counts
