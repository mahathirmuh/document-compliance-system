"""Confidence-aware finding drafts over similarity and consistency signals."""

from __future__ import annotations

from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
)
from app.schemas.similarity_internal import (
    SimilarityFindingDraft,
    SimilarityResultDraft,
    SimilarityThresholds,
)


class SimilarityFindingService:
    def build(
        self,
        results: list[SimilarityResultDraft],
        *,
        thresholds: SimilarityThresholds,
    ) -> list[SimilarityFindingDraft]:
        findings: list[SimilarityFindingDraft] = []
        seen: set[tuple[str, object, str, str]] = set()
        for result in results:
            drafts = self._for_result(result, thresholds=thresholds)
            for draft in drafts:
                key = (
                    draft.finding_code,
                    draft.translation_group_id,
                    result.source_language_code,
                    result.target_language_code,
                )
                if key not in seen:
                    seen.add(key)
                    findings.append(draft)
        return findings

    def _for_result(
        self,
        result: SimilarityResultDraft,
        *,
        thresholds: SimilarityThresholds,
    ) -> list[SimilarityFindingDraft]:
        common = {
            "translation_group_id": result.translation_group_id,
            "detected_section_id": result.detected_section_id,
            "container_id": result.container_id,
            "source_reference": result.source_reference,
            "language_code": (
                f"{result.source_language_code}-"
                f"{result.target_language_code}"
            ),
        }
        metrics = {
            "similarityScore": result.similarity_score,
            "confidence": result.confidence,
            "sourceTextHash": result.source_text_hash,
            "targetTextHash": result.target_text_hash,
            "sourceLanguage": result.source_language_code,
            "targetLanguage": result.target_language_code,
        }
        output: list[SimilarityFindingDraft] = []
        if result.analysis_status is SimilarityAnalysisStatus.SKIPPED_TOO_SHORT:
            output.append(
                self._draft(
                    "TRANSLATION_CONTENT_TOO_SHORT",
                    "INFORMATION",
                    "Translation pair is too short for similarity analysis",
                    "Review the short pair manually when it carries meaning.",
                    metrics=metrics,
                    **common,
                )
            )
            return output
        if result.similarity_category is SimilarityCategory.NOT_EVALUATED:
            reason = str(result.metrics.get("eligibilityReason") or "")
            if reason not in {
                "PAIR_LANGUAGE_MISSING",
                "PRIMARY_LANGUAGE_MISSING",
            }:
                output.append(
                    self._draft(
                        "TRANSLATION_NOT_EVALUATED",
                        "INFORMATION",
                        "Translation pair could not be evaluated",
                        "Review source quality and rerun when evidence is available.",
                        metrics=metrics,
                        **common,
                    )
                )
            return output
        required = bool(result.metrics.get("requiredPair"))
        required_section = bool(result.metrics.get("requiredSection"))
        if result.similarity_category is SimilarityCategory.LOW:
            severity = (
                "MAJOR"
                if result.confidence >= 0.80
                and (required or required_section)
                else "MINOR"
            )
            if result.confidence < 0.65:
                severity = "INFORMATION"
            output.append(
                self._draft(
                    "LOW_TRANSLATION_SIMILARITY",
                    severity,
                    "Translation pair has low semantic similarity",
                    "Have a qualified reviewer compare both language versions.",
                    metrics=metrics,
                    **common,
                )
            )
        elif result.similarity_category is SimilarityCategory.NEEDS_REVIEW:
            output.append(
                self._draft(
                    "TRANSLATION_SIMILARITY_NEEDS_REVIEW",
                    "MINOR" if result.confidence >= 0.65 else "INFORMATION",
                    "Translation similarity needs review",
                    "Review the pair; this score is a signal, not proof.",
                    metrics=metrics,
                    **common,
                )
            )
        if bool(result.metrics.get("lengthRatioAnomaly")):
            output.append(
                self._draft(
                    "TRANSLATION_LENGTH_RATIO_ANOMALY",
                    "MINOR",
                    "Translation length ratio is outside its review range",
                    "Check for omitted or added meaning.",
                    metrics={
                        **metrics,
                        "lengthRatio": result.length_ratio,
                        "expectedRange": result.metrics.get(
                            "lengthRatioRange"
                        ),
                    },
                    **common,
                )
            )
        checks = (
            (
                result.number_consistency,
                "TRANSLATION_NUMBER_MISMATCH",
                "Number values differ across translations",
                "MAJOR" if required_section else "MINOR",
            ),
            (
                result.date_consistency,
                "TRANSLATION_DATE_MISMATCH",
                "Date values differ across translations",
                "MAJOR" if required_section else "MINOR",
            ),
            (
                result.measurement_consistency,
                "TRANSLATION_MEASUREMENT_MISMATCH",
                "Measurements differ across translations",
                "MINOR",
            ),
            (
                result.reference_consistency,
                "TRANSLATION_REFERENCE_MISMATCH",
                "Document references differ across translations",
                "MAJOR" if required else "MINOR",
            ),
        )
        for check, code, title, severity in checks:
            if check.status is ConsistencyStatus.MISMATCH:
                output.append(
                    self._draft(
                        code,
                        (
                            severity
                            if result.confidence >= 0.65
                            else "INFORMATION"
                        ),
                        title,
                        "Verify the source value and each translated value.",
                        expected_value={"values": check.source_values},
                        actual_value={"values": check.target_values},
                        metrics=metrics,
                        **common,
                    )
                )
        if result.negation_consistency.status in {
            ConsistencyStatus.MISMATCH,
            ConsistencyStatus.POSSIBLE_NEGATION_MISMATCH,
        }:
            clear = (
                result.confidence >= 0.80
                and result.similarity_score is not None
                and result.similarity_score < thresholds.review
                and float(result.metrics.get("groupConfidence", 0)) >= 0.80
            )
            output.append(
                self._draft(
                    "TRANSLATION_NEGATION_MISMATCH",
                    "MAJOR" if clear else "MINOR",
                    "Possible negation mismatch across translations",
                    "A qualified reviewer must confirm the intended obligation.",
                    expected_value={
                        "values": result.negation_consistency.source_values
                    },
                    actual_value={
                        "values": result.negation_consistency.target_values
                    },
                    metrics=metrics,
                    **common,
                )
            )
        return output

    @staticmethod
    def _draft(
        finding_code: str,
        severity: str,
        title: str,
        recommendation: str,
        **values: object,
    ) -> SimilarityFindingDraft:
        return SimilarityFindingDraft(
            finding_code=finding_code,
            severity=severity,
            title=title,
            description=(
                f"{title}. Similarity is a review signal and is not legal "
                "or linguistic proof."
            ),
            recommendation=recommendation,
            **values,
        )
