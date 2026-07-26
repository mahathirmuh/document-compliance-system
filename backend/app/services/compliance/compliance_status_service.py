"""Assign a compliance status with prerequisite and review precedence."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    float_value,
    mapping,
    option,
    read,
    sequence,
    string_list,
)
from app.services.compliance.constants import ComplianceStatus
from app.services.compliance.contracts import ScoreBreakdown, StatusDecision

_OPEN_STATUSES = {"OPEN", "IN_REVIEW", "REOPENED"}
_MISSING_LANGUAGE_CODES = {
    "MISSING_INDONESIAN",
    "MISSING_ENGLISH",
    "MISSING_CHINESE",
}


class ComplianceStatusService:
    """Use explicit evidence; no status is inferred from score alone."""

    def determine(
        self,
        score: float | ScoreBreakdown,
        findings: Sequence[object] = (),
        *,
        context: object | None = None,
        rule: object | None = None,
        metrics: object | None = None,
        validator_results: Sequence[object] = (),
    ) -> StatusDecision:
        final_score = (
            score.final_score
            if isinstance(score, ScoreBreakdown)
            else float_value(score)
        )
        effective_rule = rule or (
            read(context, "rule", {}) if context is not None else {}
        )
        reasons: list[str] = []
        prerequisite_reasons = self._prerequisite_reasons(context)
        if prerequisite_reasons:
            return StatusDecision(
                status=ComplianceStatus.NOT_EVALUATED,
                reasons=tuple(prerequisite_reasons),
            )
        not_evaluated_validators = [
            enum_value(
                first(result, "validator_code", "code", default="UNKNOWN"),
            )
            for result in validator_results
            if enum_value(read(result, "status", "")).upper()
            == "NOT_EVALUATED"
        ]
        if not_evaluated_validators:
            return StatusDecision(
                status=ComplianceStatus.NOT_EVALUATED,
                reasons=tuple(
                    f"VALIDATOR_NOT_EVALUATED:{code}"
                    for code in not_evaluated_validators
                ),
            )

        open_critical = any(
            enum_value(read(finding, "status", "OPEN")).upper()
            in _OPEN_STATUSES
            and enum_value(read(finding, "severity", "")).upper()
            == "CRITICAL"
            for finding in findings
        )
        missing_languages = self._missing_languages(context, findings)
        missing_sections = self._missing_sections(context, findings)
        fail_missing_language = bool_value(
            option(
                effective_rule,
                "fail_on_missing_required_language",
                True,
            ),
            True,
        )
        fail_missing_section = bool_value(
            option(
                effective_rule,
                "fail_on_missing_required_section",
                True,
            ),
            True,
        )
        fail_critical = bool_value(
            option(effective_rule, "fail_on_critical_finding", True),
            True,
        )
        if open_critical and fail_critical:
            reasons.append("OPEN_CRITICAL_FINDING")
        if missing_languages and fail_missing_language:
            reasons.append("MISSING_REQUIRED_LANGUAGE")
        if missing_sections and fail_missing_section:
            reasons.append("MISSING_REQUIRED_SECTION")
        if reasons:
            return StatusDecision(
                status=ComplianceStatus.NON_COMPLIANT,
                reasons=tuple(reasons),
            )

        review_reasons = self._review_reasons(
            context,
            metrics,
            validator_results,
            effective_rule,
        )
        needs_review_floor = float_value(
            option(effective_rule, "needs_review_score", 0.0),
            0.0,
        )
        if review_reasons and final_score >= needs_review_floor:
            return StatusDecision(
                status=ComplianceStatus.NEEDS_REVIEW,
                reasons=tuple(review_reasons),
            )

        compliant_threshold = float_value(
            option(effective_rule, "compliant_score", 95.0),
            95.0,
        )
        partial_threshold = float_value(
            option(effective_rule, "partially_compliant_score", 70.0),
            70.0,
        )
        if (
            final_score >= compliant_threshold
            and not open_critical
            and not missing_languages
        ):
            return StatusDecision(status=ComplianceStatus.COMPLIANT)
        if final_score >= partial_threshold:
            partial_reasons: list[str] = []
            if missing_languages:
                partial_reasons.append("MISSING_REQUIRED_LANGUAGE")
            if missing_sections:
                partial_reasons.append("MISSING_REQUIRED_SECTION")
            if open_critical:
                partial_reasons.append("OPEN_CRITICAL_FINDING")
            return StatusDecision(
                status=ComplianceStatus.PARTIALLY_COMPLIANT,
                reasons=tuple(partial_reasons),
            )
        return StatusDecision(status=ComplianceStatus.NON_COMPLIANT)

    def determine_status(
        self,
        score: float | ScoreBreakdown,
        findings: Sequence[object] = (),
        **kwargs: object,
    ) -> str:
        return self.determine(
            score,
            findings,
            context=kwargs.get("context"),
            rule=kwargs.get("rule"),
            metrics=kwargs.get("metrics"),
            validator_results=sequence(kwargs.get("validator_results")),
        ).status

    assign_status = determine_status

    @staticmethod
    def _prerequisite_reasons(context: object | None) -> list[str]:
        if context is None:
            return []
        prerequisites = mapping(read(context, "prerequisites", {}))
        reasons: list[str] = []
        if not bool_value(
            first(
                prerequisites,
                "extraction_available",
                "extractionAvailable",
                default=True,
            ),
            True,
        ):
            reasons.append("COMPLIANCE_EXTRACTION_REQUIRED")
        ocr_required = bool_value(
            first(
                prerequisites,
                "ocr_required",
                "ocrRequired",
                default=False,
            ),
        )
        ocr_completed = bool_value(
            first(
                prerequisites,
                "ocr_completed",
                "ocrCompleted",
                default=True,
            ),
            True,
        )
        if ocr_required and not ocr_completed:
            reasons.append("COMPLIANCE_OCR_REQUIRED")
        if not bool_value(
            first(
                prerequisites,
                "language_detection_available",
                "languageDetectionAvailable",
                default=True,
            ),
            True,
        ):
            reasons.append("COMPLIANCE_LANGUAGE_DETECTION_REQUIRED")
        if not bool_value(
            first(
                prerequisites,
                "context_complete",
                "contextComplete",
                default=True,
            ),
            True,
        ):
            reasons.append("COMPLIANCE_CONTEXT_BUILD_FAILED")
        return reasons

    @staticmethod
    def _missing_languages(
        context: object | None,
        findings: Sequence[object],
    ) -> list[str]:
        if context is not None:
            explicit = read(context, "missing_languages", None)
            if explicit is not None:
                return string_list(explicit)
        return [
            enum_value(read(finding, "finding_code", ""))
            for finding in findings
            if enum_value(read(finding, "finding_code", "")).upper()
            in _MISSING_LANGUAGE_CODES
            and enum_value(read(finding, "status", "OPEN")).upper()
            in _OPEN_STATUSES
        ]

    @staticmethod
    def _missing_sections(
        context: object | None,
        findings: Sequence[object],
    ) -> list[str]:
        if context is not None:
            explicit = read(context, "missing_sections", None)
            if explicit is not None:
                return string_list(explicit)
        return [
            str(read(finding, "section_code", ""))
            for finding in findings
            if enum_value(read(finding, "finding_code", "")).upper()
            == "MISSING_REQUIRED_SECTION"
            and enum_value(read(finding, "status", "OPEN")).upper()
            in _OPEN_STATUSES
        ]

    @staticmethod
    def _review_reasons(
        context: object | None,
        raw_metrics: object | None,
        validator_results: Sequence[object],
        rule: object,
    ) -> list[str]:
        metrics = mapping(raw_metrics)
        if context is not None:
            context_metrics = mapping(read(context, "metrics", {}))
            metrics = {**context_metrics, **metrics}
        reasons: list[str] = []
        extraction_status = enum_value(
            first(
                metrics,
                "extraction_status",
                "extractionStatus",
                default="",
            ),
        ).upper()
        if extraction_status == "PARTIALLY_COMPLETED":
            reasons.append("EXTRACTION_PARTIALLY_COMPLETED")
        if bool_value(
            first(
                metrics,
                "ocr_confidence_too_low",
                "ocrConfidenceTooLow",
                default=False,
            ),
        ):
            reasons.append("OCR_CONFIDENCE_TOO_LOW")
        if bool_value(
            first(
                metrics,
                "manual_review_required",
                "manualReviewRequired",
                default=False,
            ),
        ):
            reasons.append("MANUAL_REVIEW_REQUIRED")
        low_confidence_percentage = float_value(
            first(
                metrics,
                "low_confidence_group_percentage",
                "lowConfidenceGroupPercentage",
                default=0.0,
            ),
        )
        review_group_threshold = float_value(
            option(rule, "low_confidence_group_review_percentage", 20.0),
            20.0,
        )
        if low_confidence_percentage > review_group_threshold:
            reasons.append("LOW_GROUPING_CONFIDENCE")
        unknown_percentage = float_value(
            first(
                metrics,
                "unknown_block_percentage",
                "unknownBlockPercentage",
                default=0.0,
            ),
        )
        unknown_threshold = float_value(
            option(rule, "maximum_unknown_block_percentage", 10.0),
            10.0,
        )
        if unknown_percentage > unknown_threshold:
            reasons.append("UNKNOWN_TEXT_EXCEEDS_THRESHOLD")
        for result in validator_results:
            if enum_value(read(result, "status", "")).upper() == "NEEDS_REVIEW":
                code = enum_value(
                    first(
                        result,
                        "validator_code",
                        "code",
                        default="UNKNOWN",
                    ),
                )
                reasons.append(f"VALIDATOR_NEEDS_REVIEW:{code}")
        return list(dict.fromkeys(reasons))

