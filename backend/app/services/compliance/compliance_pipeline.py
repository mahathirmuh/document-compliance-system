"""Side-effect-free Phase 8 section/group/validator/score pipeline."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from celery.exceptions import SoftTimeLimitExceeded

from app.schemas.compliance_internal import ComplianceValidationContext
from app.services.compliance._compat import (
    bool_value,
    first,
    float_value,
)
from app.services.compliance.compliance_context_service import (
    ComplianceContextBuildError,
    ComplianceContextService,
)
from app.services.compliance.compliance_score_service import (
    ComplianceScoreService,
)
from app.services.compliance.compliance_status_service import (
    ComplianceStatusService,
)
from app.services.compliance.constants import FindingCode, FindingSeverity
from app.services.compliance.contracts import CompliancePipelineResult
from app.services.compliance.findings.finding_deduplication_service import (
    FindingDeduplicationService,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.grouping.translation_group_service import (
    TranslationGroupService,
)
from app.services.compliance.sections.section_detector import SectionDetector
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)
from app.services.compliance.validators.cell_multilingual_validator import (
    CellMultilingualValidator,
)
from app.services.compliance.validators.container_completeness_validator import (
    ContainerCompletenessValidator,
)
from app.services.compliance.validators.document_code_validator import (
    DocumentCodeValidator,
)
from app.services.compliance.validators.language_coverage_validator import (
    LanguageCoverageValidator,
)
from app.services.compliance.validators.language_order_validator import (
    LanguageOrderValidator,
)
from app.services.compliance.validators.language_presence_validator import (
    LanguagePresenceValidator,
)
from app.services.compliance.validators.required_section_validator import (
    RequiredSectionValidator,
)
from app.services.compliance.validators.section_detection_validator import (
    SectionDetectionValidator,
)
from app.services.compliance.validators.section_order_validator import (
    SectionOrderValidator,
)
from app.services.compliance.validators.table_multilingual_validator import (
    TableMultilingualValidator,
)
from app.services.compliance.validators.translation_group_validator import (
    TranslationGroupValidator,
)

CancellationCheck = Callable[[], bool | Awaitable[bool]]
ProgressCallback = Callable[[str, int], None | Awaitable[None]]
StageResultT = TypeVar("StageResultT")

COMPLIANCE_SECTION_DETECTION_FAILED = "COMPLIANCE_SECTION_DETECTION_FAILED"
COMPLIANCE_GROUPING_FAILED = "COMPLIANCE_GROUPING_FAILED"
COMPLIANCE_VALIDATION_FAILED = "COMPLIANCE_VALIDATION_FAILED"

_SECTION_DETECTION_FAILED_MESSAGE = "Document section detection could not be completed."
_GROUPING_FAILED_MESSAGE = "Multilingual content grouping could not be completed."
_VALIDATION_FAILED_MESSAGE = "Compliance validation could not be completed."


class CompliancePipelineCancelled(RuntimeError):
    code = "COMPLIANCE_CANCELLED"


class CompliancePipelineStageError(RuntimeError):
    """Stable public failure contract for one in-memory pipeline stage."""

    def __init__(self, code: str, public_message: str) -> None:
        self.code = code
        self.public_message = public_message
        super().__init__(public_message)


class CompliancePipeline:
    """Run all algorithms in memory; persistence is an outer transaction."""

    def __init__(
        self,
        *,
        section_detector: SectionDetector | None = None,
        grouping_service: TranslationGroupService | None = None,
        validators: Sequence[BaseComplianceValidator] | None = None,
        score_service: ComplianceScoreService | None = None,
        status_service: ComplianceStatusService | None = None,
        deduplication_service: FindingDeduplicationService | None = None,
        context_service: ComplianceContextService | None = None,
    ) -> None:
        self.section_detector = section_detector or SectionDetector()
        self.grouping_service = grouping_service or TranslationGroupService()
        self.validators = tuple(
            validators
            or (
                DocumentCodeValidator(),
                LanguagePresenceValidator(),
                LanguageCoverageValidator(),
                ContainerCompletenessValidator(),
                SectionDetectionValidator(),
                RequiredSectionValidator(),
                SectionOrderValidator(),
                LanguageOrderValidator(),
                TranslationGroupValidator(),
                TableMultilingualValidator(),
                CellMultilingualValidator(),
            ),
        )
        self.score_service = score_service or ComplianceScoreService()
        self.status_service = status_service or ComplianceStatusService()
        self.deduplication = deduplication_service or FindingDeduplicationService()
        self.context_service = context_service or ComplianceContextService()
        self.finding_factory = FindingFactory()

    async def run(
        self,
        context: ComplianceValidationContext,
        *,
        cancellation_check: CancellationCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        previous_findings: Sequence[object] = (),
    ) -> CompliancePipelineResult:
        await self._check_cancelled(cancellation_check)
        sections = list(context.detected_sections)
        if context.rule.validate_sections and not sections:
            sections = self._run_stage(
                COMPLIANCE_SECTION_DETECTION_FAILED,
                _SECTION_DETECTION_FAILED_MESSAGE,
                lambda: self.section_detector.detect(
                    context.blocks,
                    context.section_aliases,
                    required_sections=context.rule.required_sections,
                    profile_id=context.rule.section_alias_profile_id,
                    allow_repeated_sections=bool_value(
                        first(
                            context.rule.validation_options,
                            "allow_repeated_sections",
                            "allowRepeatedSections",
                            default=False,
                        ),
                    ),
                ),
            )
        await self._notify(progress_callback, "DETECTING_SECTIONS", 15)
        await self._check_cancelled(cancellation_check)
        groups = list(context.translation_groups)
        grouping_required = any(
            (
                context.rule.validate_language_order,
                context.rule.validate_translation_groups,
                context.rule.validate_tables,
                context.rule.validate_cells,
            ),
        )
        if grouping_required and not groups:
            groups = self._run_stage(
                COMPLIANCE_GROUPING_FAILED,
                _GROUPING_FAILED_MESSAGE,
                lambda: self.grouping_service.group(
                    context,
                    context.rule.required_languages,
                    source_format=context.source_format,
                    tables=context.tables,
                    sections=sections,
                ),
            )
        await self._notify(progress_callback, "GROUPING_CONTENT", 30)
        evaluated_context = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self.context_service.with_analysis(
                context,
                detected_sections=sections,
                translation_groups=groups,
            ),
        )
        results = []
        generated_findings = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self._quality_findings(evaluated_context),
        )
        stage = ""
        for validator in self.validators:
            await self._check_cancelled(cancellation_check)
            validator_code = validator.code
            next_stage, progress = self._run_stage(
                COMPLIANCE_VALIDATION_FAILED,
                _VALIDATION_FAILED_MESSAGE,
                lambda: self._validator_progress(validator_code),
            )
            if next_stage != stage:
                stage = next_stage
                await self._notify(
                    progress_callback,
                    next_stage,
                    progress,
                )
            validator_result = await self._run_async_stage(
                COMPLIANCE_VALIDATION_FAILED,
                _VALIDATION_FAILED_MESSAGE,
                validator.validate(evaluated_context),
            )
            current_findings = validator_result.findings
            validator_findings = self._run_stage(
                COMPLIANCE_VALIDATION_FAILED,
                _VALIDATION_FAILED_MESSAGE,
                lambda: tuple(current_findings),
            )
            results.append(validator_result)
            generated_findings.extend(validator_findings)
        await self._notify(progress_callback, "GENERATING_FINDINGS", 88)
        findings = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self.deduplication.deduplicate(generated_findings),
        )
        if previous_findings:
            findings = self._run_stage(
                COMPLIANCE_VALIDATION_FAILED,
                _VALIDATION_FAILED_MESSAGE,
                lambda: self.deduplication.merge_revalidation(
                    findings,
                    previous_findings,
                ),
            )
        await self._notify(progress_callback, "CALCULATING_SCORE", 93)
        score = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self.score_service.calculate(
                results,
                findings,
                evaluated_context.rule,
            ),
        )
        aggregate_metrics = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self._aggregate_metrics(
                evaluated_context,
                results,
            ),
        )
        status = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: self.status_service.determine(
                score,
                findings,
                context=evaluated_context,
                rule=evaluated_context.rule,
                metrics=aggregate_metrics,
                validator_results=results,
            ),
        )
        warnings = self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: tuple(
                dict.fromkeys(
                    [
                        *evaluated_context.warnings,
                        *(
                            warning
                            for validator_result in results
                            for warning in validator_result.warnings
                        ),
                    ],
                ),
            ),
        )
        return self._run_stage(
            COMPLIANCE_VALIDATION_FAILED,
            _VALIDATION_FAILED_MESSAGE,
            lambda: CompliancePipelineResult(
                context=evaluated_context,
                validator_results=tuple(results),
                findings=tuple(findings),
                score=score,
                status=status,
                warnings=warnings,
            ),
        )

    validate = run

    async def _check_cancelled(
        self,
        checker: CancellationCheck | None,
    ) -> None:
        if checker is None:
            return
        decision = checker()
        if inspect.isawaitable(decision):
            decision = await decision
        if decision:
            raise CompliancePipelineCancelled(
                "Compliance validation was cancelled.",
            )

    @staticmethod
    async def _notify(
        callback: ProgressCallback | None,
        stage: str,
        progress: int,
    ) -> None:
        if callback is None:
            return
        result = callback(stage, progress)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _run_stage(
        code: str,
        public_message: str,
        operation: Callable[[], StageResultT],
    ) -> StageResultT:
        try:
            return operation()
        except (
            ComplianceContextBuildError,
            CompliancePipelineCancelled,
            CompliancePipelineStageError,
            SoftTimeLimitExceeded,
        ):
            raise
        except Exception as exc:
            raise CompliancePipelineStageError(
                code,
                public_message,
            ) from exc

    @staticmethod
    async def _run_async_stage(
        code: str,
        public_message: str,
        operation: Awaitable[StageResultT],
    ) -> StageResultT:
        try:
            return await operation
        except (
            ComplianceContextBuildError,
            CompliancePipelineCancelled,
            CompliancePipelineStageError,
            SoftTimeLimitExceeded,
        ):
            raise
        except Exception as exc:
            raise CompliancePipelineStageError(
                code,
                public_message,
            ) from exc

    @staticmethod
    def _validator_progress(code: str) -> tuple[str, int]:
        normalized = str(code).upper()
        if normalized in {
            "DOCUMENT_CODE",
            "LANGUAGE_PRESENCE",
            "LANGUAGE_COVERAGE",
            "CONTAINER_COMPLETENESS",
        }:
            return "VALIDATING_LANGUAGES", 45
        if normalized in {
            "SECTION_DETECTION",
            "REQUIRED_SECTIONS",
            "SECTION_ORDER",
        }:
            return "VALIDATING_SECTIONS", 60
        if normalized in {"LANGUAGE_ORDER", "TRANSLATION_GROUPS"}:
            return "VALIDATING_ORDER", 70
        return "VALIDATING_TABLES", 80

    def _quality_findings(
        self,
        context: ComplianceValidationContext,
    ) -> list[object]:
        prerequisites = context.prerequisites
        findings: list[object] = []
        if bool_value(
            first(
                prerequisites,
                "ocr_required",
                "ocrRequired",
                default=False,
            ),
        ) and not bool_value(
            first(
                prerequisites,
                "ocr_completed",
                "ocrCompleted",
                default=True,
            ),
            True,
        ):
            findings.append(
                self.finding_factory.create(
                    FindingCode.OCR_REQUIRED_NOT_COMPLETED,
                    severity=FindingSeverity.CRITICAL,
                ),
            )
        extraction_status = str(
            first(
                prerequisites,
                "extraction_status",
                "extractionStatus",
                default="",
            ),
        ).upper()
        if extraction_status == "PARTIALLY_COMPLETED":
            findings.append(
                self.finding_factory.create(
                    FindingCode.EXTRACTION_PARTIALLY_COMPLETED,
                    severity=FindingSeverity.INFORMATION,
                ),
            )
        if bool_value(
            first(
                prerequisites,
                "ocr_confidence_too_low",
                "ocrConfidenceTooLow",
                default=False,
            ),
        ):
            findings.append(
                self.finding_factory.create(
                    FindingCode.OCR_CONFIDENCE_TOO_LOW,
                    severity=FindingSeverity.INFORMATION,
                ),
            )
        return findings

    @staticmethod
    def _aggregate_metrics(
        context: ComplianceValidationContext,
        results: Sequence[object],
    ) -> dict[str, object]:
        metrics: dict[str, object] = {}
        for result in results:
            code = str(read(result, "validator_code", "")).upper()
            result_metrics = read(result, "metrics", {})
            if not isinstance(result_metrics, dict):
                continue
            if code == "LANGUAGE_COVERAGE":
                metrics["unknownBlockPercentage"] = float_value(
                    result_metrics.get("unknownBlockPercentage"),
                )
                metrics["mixedBlockPercentage"] = float_value(
                    result_metrics.get("mixedBlockPercentage"),
                )
            if code == "TRANSLATION_GROUPS":
                total = int(result_metrics.get("totalGroups", 0))
                low = int(result_metrics.get("lowConfidenceGroups", 0))
                metrics["lowConfidenceGroupPercentage"] = (
                    low * 100.0 / total if total else 0.0
                )
        metrics.update(context.prerequisites)
        return metrics


def read(value: object, name: str, default: object = None) -> object:
    """Local import-cycle-free field reader used only by metric aggregation."""

    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
