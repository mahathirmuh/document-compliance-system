"""Atomic persistence adapter for one completed compliance pipeline result."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.models.audit_log import AuditLog
from app.models.compliance_enums import (
    ComplianceJobStatus,
    ComplianceRunStatus,
    ComplianceStatus,
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
    SectionAliasMatchType,
    SectionLanguagePresenceStatus,
    TranslationGroupType,
)
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.detected_section import DetectedSection
from app.models.finding_occurrence import FindingOccurrence
from app.models.section_language_result import SectionLanguageResult
from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.models.validation_finding import ValidationFinding
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.detected_section_repository import (
    DetectedSectionRepository,
)
from app.repositories.section_language_result_repository import (
    SectionLanguageResultRepository,
)
from app.repositories.translation_group_repository import (
    TranslationGroupRepository,
)
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.schemas.compliance_internal import (
    ComplianceBlockData,
    ComplianceValidationContext,
    FindingDraft,
    TranslationGroupMemberData,
    ValidatorResult,
)
from app.services.compliance._compat import enum_value, json_safe, mapping
from app.services.compliance.contracts import CompliancePipelineResult
from app.utils.datetime import utc_now

_OPEN_FINDING_STATUSES = {
    FindingStatus.OPEN,
    FindingStatus.IN_REVIEW,
    FindingStatus.REOPENED,
}
_COMPONENT_VALIDATORS = {
    "document_code_score": "DOCUMENT_CODE",
    "language_presence_score": "LANGUAGE_PRESENCE",
    "language_coverage_score": "LANGUAGE_COVERAGE",
    "section_completeness_score": "REQUIRED_SECTIONS",
    "language_order_score": "LANGUAGE_ORDER",
    "translation_group_score": "TRANSLATION_GROUPS",
    "table_completeness_score": "TABLE_MULTILINGUAL",
}


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(round(float(value), 4)))


def _uuid(value: object | None) -> UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _json_mapping(value: object) -> dict[str, object]:
    safe = json_safe(value)
    return (
        {str(key): item for key, item in safe.items()}
        if isinstance(safe, dict)
        else {}
    )


class CompliancePersistenceService:
    """Persist a fully built result in the caller's single transaction."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self.session = session
        self.batch_size = settings.compliance_db_batch_size
        self.runs = ComplianceRunRepository(session)
        self.sections = DetectedSectionRepository(session)
        self.section_languages = SectionLanguageResultRepository(session)
        self.groups = TranslationGroupRepository(session)
        self.findings = ValidationFindingRepository(session)

    async def persist(
        self,
        job: ComplianceJob,
        result: CompliancePipelineResult,
        *,
        completed_at: datetime | None = None,
    ) -> ComplianceRun:
        """Write run, children, findings, latest pointer, and job outcome."""

        context = result.context
        if not isinstance(context, ComplianceValidationContext):
            context = ComplianceValidationContext.model_validate(context)
        completed = completed_at or utc_now()
        source_content_hash = (
            job.source_content_hash or context.source_content_hash
        )
        if source_content_hash is None:
            raise ValueError(
                "A resolved source-content hash is required for persistence."
            )
        run_status = self._run_status(result)
        component_scores = self._component_scores(result)
        detected_languages = self._detected_languages(
            result,
            context,
        )
        missing_languages = [
            language
            for language in context.rule.required_languages
            if language not in detected_languages
        ]
        detected_section_codes = [
            section.canonical_code
            for section in context.detected_sections
        ]
        missing_sections = [
            code
            for code in context.rule.required_sections
            if code not in detected_section_codes
        ]
        finding_drafts = cast(Sequence[FindingDraft], result.findings)
        severity_counts = Counter(
            FindingSeverity(str(finding.severity))
            for finding in finding_drafts
        )
        open_findings = sum(
            FindingStatus(str(finding.status)) in _OPEN_FINDING_STATUSES
            for finding in finding_drafts
        )
        metrics = self._run_metrics(result)
        run = ComplianceRun(
            compliance_job_id=job.id,
            document_id=job.document_id,
            document_revision_id=job.document_revision_id,
            document_file_id=job.document_file_id,
            extraction_run_id=job.extraction_run_id,
            ocr_run_id=job.ocr_run_id,
            language_detection_run_id=job.language_detection_run_id,
            validation_rule_id=job.validation_rule_id,
            rule_snapshot_json=context.rule.model_dump(
                mode="json",
                by_alias=True,
            ),
            source_content_hash=source_content_hash,
            status=run_status,
            compliance_status=ComplianceStatus(result.status.status),
            compliance_score=_decimal(result.score.final_score),
            maximum_score=_decimal(result.score.maximum_score),
            **component_scores,
            total_findings=len(result.findings),
            critical_findings=severity_counts[FindingSeverity.CRITICAL],
            major_findings=severity_counts[FindingSeverity.MAJOR],
            minor_findings=severity_counts[FindingSeverity.MINOR],
            information_findings=severity_counts[
                FindingSeverity.INFORMATION
            ],
            open_findings=open_findings,
            required_languages_json=list(context.rule.required_languages),
            detected_languages_json=detected_languages,
            missing_languages_json=missing_languages,
            required_sections_json=list(context.rule.required_sections),
            detected_sections_json=detected_section_codes,
            missing_sections_json=missing_sections,
            warnings_json=list(result.warnings),
            metrics_json=metrics,
            started_at=job.started_at or completed,
            completed_at=completed,
            requested_by=job.requested_by,
        )
        await self.runs.add(run)

        persisted_sections = await self._persist_sections(
            run,
            context,
        )
        section_by_code = self._section_by_code(persisted_sections)
        persisted_groups = await self._persist_groups(
            run,
            context,
            section_by_code,
        )
        group_by_index = {
            group.group_index: group for group in persisted_groups
        }
        persisted_findings = await self._persist_findings(
            run,
            job,
            finding_drafts,
            section_by_code,
            group_by_index,
        )
        await self.runs.set_latest_for_file(
            document_file_id=job.document_file_id,
            compliance_run_id=run.id,
        )
        job.status = (
            ComplianceJobStatus.PARTIALLY_COMPLETED
            if run_status is ComplianceRunStatus.PARTIALLY_COMPLETED
            else ComplianceJobStatus.COMPLETED
        )
        job.progress = 100
        job.current_stage = "Completed"
        job.completed_at = completed
        job.error_code = None
        job.error_message = None
        job.error_details_json = None
        job.result_summary_json = {
            "runId": str(run.id),
            "complianceStatus": run.compliance_status.value,
            "complianceScore": float(run.compliance_score),
            "totalFindings": len(persisted_findings),
            "criticalFindings": severity_counts[
                FindingSeverity.CRITICAL
            ],
            "majorFindings": severity_counts[FindingSeverity.MAJOR],
            "minorFindings": severity_counts[FindingSeverity.MINOR],
        }
        await self.session.flush()
        return run

    @staticmethod
    def _detected_languages(
        result: CompliancePipelineResult,
        context: ComplianceValidationContext,
    ) -> list[str]:
        """Use the validator's evidence thresholds for retained presence."""

        validator_results = cast(
            Sequence[ValidatorResult],
            result.validator_results,
        )
        for validator in validator_results:
            if (
                enum_value(validator.validator_code).upper()
                != "LANGUAGE_PRESENCE"
            ):
                continue
            presence = mapping(validator.metrics.get("presence", {}))
            if presence:
                return [
                    language
                    for language in context.rule.required_languages
                    if enum_value(presence.get(language)).upper()
                    == "PRESENT"
                ]
            break
        return [
            language
            for language in context.rule.required_languages
            if any(
                block.language_code == language
                and block.eligibility_status == "ELIGIBLE"
                for block in context.blocks
            )
        ]

    async def _persist_sections(
        self,
        run: ComplianceRun,
        context: ComplianceValidationContext,
    ) -> list[DetectedSection]:
        definitions = {
            alias.canonical_code: alias.section_definition_id
            for alias in context.section_aliases
            if alias.section_definition_id is not None
        }
        items = [
            DetectedSection(
                compliance_run_id=run.id,
                section_definition_id=definitions.get(
                    section.canonical_code
                ),
                canonical_code=section.canonical_code,
                container_id=section.container_id,
                start_block_id=section.start_block_id,
                end_block_id=section.end_block_id,
                heading_block_id=section.heading_block_id,
                heading_text=section.heading_text,
                heading_language_code=section.heading_language_code,
                match_type=SectionAliasMatchType(section.match_type),
                match_confidence=_decimal(section.match_confidence),
                section_order=section.section_order,
                is_required=section.is_required,
                is_complete=section.is_complete,
                language_presence_json=dict(section.language_presence),
                metrics_json=dict(section.metrics),
            )
            for section in context.detected_sections
        ]
        await self.sections.add_many(items, batch_size=self.batch_size)
        language_rows: list[SectionLanguageResult] = []
        context_sections = list(context.detected_sections)
        for persisted, source in zip(items, context_sections, strict=True):
            language_rows.extend(
                self._section_language_rows(
                    persisted,
                    source.container_id,
                    source.start_block_order,
                    source.end_block_order,
                    context,
                )
            )
        await self.section_languages.add_many(
            language_rows,
            batch_size=self.batch_size,
        )
        return items

    @staticmethod
    def _section_language_rows(
        section: DetectedSection,
        container_id: UUID | None,
        start_order: int,
        end_order: int,
        context: ComplianceValidationContext,
    ) -> list[SectionLanguageResult]:
        section_blocks = [
            block
            for block in context.blocks
            if block.container_id == container_id
            and start_order <= block.block_order <= end_order
            and block.eligibility_status == "ELIGIBLE"
        ]
        total_characters = sum(block.character_count for block in section_blocks)
        rows: list[SectionLanguageResult] = []
        presence: dict[str, str] = {}
        for language in context.rule.required_languages:
            blocks = [
                block
                for block in section_blocks
                if block.language_code == language
            ]
            characters = sum(block.character_count for block in blocks)
            status = (
                SectionLanguagePresenceStatus.PRESENT
                if blocks and characters
                else SectionLanguagePresenceStatus.NOT_PRESENT
            )
            presence[language] = status.value
            rows.append(
                SectionLanguageResult(
                    detected_section_id=section.id,
                    language_code=language,
                    presence_status=status,
                    block_count=len(blocks),
                    character_count=characters,
                    coverage_percentage=_decimal(
                        characters * 100 / total_characters
                        if total_characters
                        else 0
                    ),
                    average_confidence=(
                        _decimal(
                            sum(
                                block.language_confidence
                                for block in blocks
                            )
                            / len(blocks)
                        )
                        if blocks
                        else None
                    ),
                    first_block_id=blocks[0].id if blocks else None,
                    last_block_id=blocks[-1].id if blocks else None,
                    metrics_json={"eligibleSectionBlocks": len(section_blocks)},
                )
            )
        section.language_presence_json = presence
        section.is_complete = (
            not section.is_required
            or all(
                value == SectionLanguagePresenceStatus.PRESENT.value
                for value in presence.values()
            )
        )
        return rows

    async def _persist_groups(
        self,
        run: ComplianceRun,
        context: ComplianceValidationContext,
        section_by_code: dict[str, DetectedSection],
    ) -> list[TranslationGroup]:
        groups: list[TranslationGroup] = []
        source_groups = list(context.translation_groups)
        for source in source_groups:
            section = (
                section_by_code.get(source.detected_section_code)
                if source.detected_section_code
                else None
            )
            groups.append(
                TranslationGroup(
                    compliance_run_id=run.id,
                    container_id=source.container_id,
                    detected_section_id=section.id if section else None,
                    group_index=source.group_index,
                    group_type=TranslationGroupType(source.group_type),
                    start_block_order=source.start_block_order,
                    end_block_order=source.end_block_order,
                    source_reference=source.source_reference,
                    expected_languages_json=list(
                        source.expected_languages
                    ),
                    detected_languages_json=list(
                        source.detected_languages
                    ),
                    language_order_json=list(source.language_order),
                    is_complete=source.is_complete,
                    is_order_valid=source.is_order_valid,
                    confidence=_decimal(source.confidence),
                    metrics_json=dict(source.metrics),
                )
            )
        await self.groups.add_many(groups, batch_size=self.batch_size)
        members: list[TranslationGroupMember] = []
        block_by_id = {
            block.id: block for block in context.blocks if block.id is not None
        }
        for persisted, source in zip(groups, source_groups, strict=True):
            for member in source.members:
                values = self._member_source_values(
                    member,
                    block_by_id.get(cast(UUID, member.block_id)),
                )
                if not any(
                    values[key]
                    for key in (
                        "extracted_block_id",
                        "ocr_block_id",
                        "language_block_result_id",
                    )
                ):
                    # Retain the official group without inventing a source FK.
                    # This can occur for inferred empty table positions.
                    continue
                members.append(
                    TranslationGroupMember(
                        translation_group_id=persisted.id,
                        language_code=member.language_code,
                        source_type=values["source_type"],
                        extracted_block_id=values["extracted_block_id"],
                        ocr_block_id=values["ocr_block_id"],
                        language_block_result_id=values[
                            "language_block_result_id"
                        ],
                        block_order=member.block_order,
                        text_snapshot=member.text_snapshot[:2000],
                        confidence=_decimal(member.confidence),
                        position_json=dict(member.position),
                    )
                )
        await self.groups.add_members(members, batch_size=self.batch_size)
        return groups

    @staticmethod
    def _member_source_values(
        member: TranslationGroupMemberData,
        block: ComplianceBlockData | None,
    ) -> dict[str, object | None]:
        metadata = block.metadata if block is not None else {}
        annotation = metadata.get("languageAnnotation", {})
        if not isinstance(annotation, dict):
            annotation = {}
        source_type = (
            member.source_type
            or str(
                metadata.get("sourceType")
                or annotation.get("sourceType")
                or ""
            )
            or "STRUCTURAL"
        )
        block_id = member.block_id or (block.id if block else None)
        extracted_id = member.extracted_block_id
        ocr_id = member.ocr_block_id
        if extracted_id is None and ocr_id is None and block_id is not None:
            if source_type == "NATIVE_EXTRACTION":
                extracted_id = block_id
            elif source_type == "OCR":
                ocr_id = block_id
        language_result_id = member.language_block_result_id or _uuid(
            metadata.get("languageBlockResultId")
            or annotation.get("languageBlockResultId")
        )
        return {
            "source_type": source_type,
            "extracted_block_id": extracted_id,
            "ocr_block_id": ocr_id,
            "language_block_result_id": language_result_id,
        }

    async def _persist_findings(
        self,
        run: ComplianceRun,
        job: ComplianceJob,
        drafts: Sequence[object],
        section_by_code: dict[str, DetectedSection],
        group_by_index: dict[int, TranslationGroup],
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        for raw in drafts:
            draft = (
                raw
                if isinstance(raw, FindingDraft)
                else FindingDraft.model_validate(raw)
            )
            section = (
                section_by_code.get(draft.detected_section_code)
                if draft.detected_section_code
                else None
            )
            group_index = draft.metrics.get("groupIndex")
            group = (
                group_by_index.get(int(group_index))
                if group_index is not None
                else None
            )
            findings.append(
                ValidationFinding(
                    compliance_run_id=run.id,
                    document_id=job.document_id,
                    document_revision_id=job.document_revision_id,
                    document_file_id=job.document_file_id,
                    validation_rule_id=job.validation_rule_id,
                    finding_code=FindingCode(draft.finding_code),
                    finding_type=FindingType(draft.finding_type),
                    severity=FindingSeverity(draft.severity),
                    status=FindingStatus(draft.status),
                    title=draft.title,
                    description=draft.description,
                    recommendation=draft.recommendation,
                    container_id=draft.container_id,
                    detected_section_id=(
                        draft.detected_section_id
                        or (section.id if section else None)
                    ),
                    translation_group_id=(
                        draft.translation_group_id
                        or (group.id if group else None)
                    ),
                    extracted_block_id=draft.extracted_block_id,
                    ocr_block_id=draft.ocr_block_id,
                    page_number=draft.page_number,
                    worksheet_name=draft.worksheet_name,
                    cell_coordinate=draft.cell_coordinate,
                    source_reference=draft.source_reference,
                    location_json=dict(draft.location),
                    language_code=draft.language_code,
                    expected_value_json=draft.expected_value,
                    actual_value_json=draft.actual_value,
                    metrics_json={
                        **dict(draft.metrics),
                        **(
                            {
                                "deduplicationKey": (
                                    draft.deduplication_key
                                )
                            }
                            if draft.deduplication_key
                            else {}
                        ),
                        **(
                            {
                                "detectedSectionCode": (
                                    draft.detected_section_code
                                )
                            }
                            if draft.detected_section_code
                            else {}
                        ),
                        **(
                            {
                                "translationGroupSignature": (
                                    draft.translation_group_signature
                                )
                            }
                            if draft.translation_group_signature
                            else {}
                        ),
                    },
                    is_system_generated=True,
                    is_repeat=draft.is_system_generated
                    and bool(
                        getattr(raw, "is_repeat", False)
                        if not isinstance(raw, dict)
                        else raw.get("is_repeat", False)
                    ),
                    previous_finding_id=_uuid(
                        getattr(raw, "previous_finding_id", None)
                        if not isinstance(raw, dict)
                        else raw.get("previous_finding_id")
                    ),
                    created_by=None,
                )
            )
        await self.findings.add_many(
            findings,
            batch_size=self.batch_size,
        )
        await self.findings.add_occurrences(
            [
                FindingOccurrence(
                    finding_id=finding.id,
                    compliance_run_id=run.id,
                    source_reference=finding.source_reference,
                    location_json=dict(finding.location_json),
                    metrics_json=dict(finding.metrics_json),
                )
                for finding in findings
            ],
            batch_size=self.batch_size,
        )
        await self._persist_finding_audits(run, job, findings)
        return findings

    async def _persist_finding_audits(
        self,
        run: ComplianceRun,
        job: ComplianceJob,
        findings: Sequence[ValidationFinding],
    ) -> None:
        """Record minimal creation history in the same result transaction."""

        for offset in range(0, len(findings), self.batch_size):
            batch = [
                AuditLog(
                    user_id=job.requested_by,
                    action=AuditAction.CREATE_FINDING,
                    entity_type="ValidationFinding",
                    entity_id=finding.id,
                    description="Compliance finding generated.",
                    new_values_json={
                        "complianceRunId": str(run.id),
                        "findingCode": finding.finding_code.value,
                        "findingType": finding.finding_type.value,
                        "severity": finding.severity.value,
                        "status": finding.status.value,
                        "isSystemGenerated": True,
                    },
                )
                for finding in findings[offset : offset + self.batch_size]
            ]
            self.session.add_all(batch)
            await self.session.flush()

    @staticmethod
    def _section_by_code(
        sections: Sequence[DetectedSection],
    ) -> dict[str, DetectedSection]:
        result: dict[str, DetectedSection] = {}
        for section in sections:
            result.setdefault(section.canonical_code, section)
        return result

    @staticmethod
    def _run_status(
        result: CompliancePipelineResult,
    ) -> ComplianceRunStatus:
        validator_results = cast(
            Sequence[ValidatorResult],
            result.validator_results,
        )
        partial = bool(result.warnings) or any(
            str(validator.status) in {"NOT_EVALUATED", "NEEDS_REVIEW"}
            for validator in validator_results
        )
        return (
            ComplianceRunStatus.PARTIALLY_COMPLETED
            if partial
            else ComplianceRunStatus.COMPLETED
        )

    @staticmethod
    def _component_scores(
        result: CompliancePipelineResult,
    ) -> dict[str, Decimal]:
        validator_results = cast(
            Sequence[ValidatorResult],
            result.validator_results,
        )
        by_code = {
            str(validator.validator_code): _decimal(validator.score)
            for validator in validator_results
        }
        return {
            field: by_code.get(code, Decimal(0))
            for field, code in _COMPONENT_VALIDATORS.items()
        }

    @staticmethod
    def _run_metrics(
        result: CompliancePipelineResult,
    ) -> dict[str, object]:
        validator_results = cast(
            Sequence[ValidatorResult],
            result.validator_results,
        )
        metrics: dict[str, object] = {
            "scoreBreakdown": {
                "weightedScore": result.score.weighted_score,
                "majorPenalty": result.score.major_penalty,
                "minorPenalty": result.score.minor_penalty,
                "totalPenalty": result.score.total_penalty,
                "scoreBeforeCap": result.score.score_before_cap,
                "scoreCap": result.score.score_cap,
                "finalScore": result.score.final_score,
                "maximumScore": result.score.maximum_score,
                "validators": result.score.validators,
                "findingCounts": result.score.finding_counts,
            },
            "statusReasons": list(result.status.reasons),
            "validators": {
                str(validator.validator_code): {
                    "status": str(validator.status),
                    "score": validator.score,
                    "maximumScore": validator.maximum_score,
                    "metrics": dict(validator.metrics),
                    "warnings": list(validator.warnings),
                }
                for validator in validator_results
            },
            "structuralValidationOnly": True,
            "semanticSimilarityEvaluated": False,
        }
        return _json_mapping(metrics)
