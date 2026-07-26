"""Atomic persistence for completed glossary validation results."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, cast

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.document_file import DocumentFile
from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossarySourceType,
    GlossaryValidationStatus,
)
from app.models.glossary_match import GlossaryMatch
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.validation_finding import ValidationFinding
from app.repositories.audit_log import AuditLogRepository
from app.repositories.glossary_match_repository import (
    GlossaryMatchRepository,
)
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.services.compliance.findings.finding_deduplication_service import (
    FindingDeduplicationService,
)
from app.services.glossary.contracts import (
    GlossaryFindingSignal,
    GlossaryValidationResult,
)
from app.utils.datetime import utc_now

if TYPE_CHECKING:
    from collections.abc import Sequence


class GlossaryPersistenceService:
    """Persist matches and Phase 8 workflow findings in one transaction."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 1000,
    ) -> None:
        self.session = session
        self.batch_size = max(1, batch_size)
        self.matches = GlossaryMatchRepository(session)
        self.findings = ValidationFindingRepository(session)
        self.deduplication = FindingDeduplicationService()
        self.audit_logs = AuditLogRepository(session)

    async def persist(
        self,
        run: GlossaryValidationRun,
        result: GlossaryValidationResult,
        *,
        completed_at: datetime | None = None,
    ) -> tuple[list[GlossaryMatch], list[ValidationFinding]]:
        completed = completed_at or utc_now()
        match_rows = [
            GlossaryMatch(
                glossary_validation_run_id=run.id,
                glossary_term_id=item.glossary_term_id,
                glossary_translation_id=item.glossary_translation_id,
                glossary_variant_id=item.glossary_variant_id,
                language_code=GlossaryLanguageCode(item.language_code),
                source_type=GlossarySourceType(item.source_type),
                extracted_block_id=item.extracted_block_id,
                ocr_block_id=item.ocr_block_id,
                container_id=item.container_id,
                detected_section_id=item.detected_section_id,
                source_reference=item.source_reference[:1000],
                matched_text=item.matched_text[:500],
                normalised_matched_text=(
                    item.normalised_matched_text[:500]
                ),
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                match_type=GlossaryMatchType(item.match_type),
                is_preferred=item.is_preferred,
                is_forbidden=item.is_forbidden,
                exception_id=item.exception_id,
                metadata_json={
                    **item.metadata,
                    "confidence": item.confidence,
                    "isAllowedVariant": item.is_allowed_variant,
                },
            )
            for item in result.matches
        ]
        await self.matches.add_many(
            match_rows,
            batch_size=self.batch_size,
        )
        previous_findings = await self._previous_findings(run)
        current_signals = [
            replace(
                item,
                document_revision_id=run.document_revision_id,
            )
            for item in result.findings
        ]
        linked = cast(
            list[GlossaryFindingSignal],
            self.deduplication.link_repeated(
                self.deduplication.deduplicate(current_signals),
                previous_findings,
            ),
        )
        finding_rows = [
            self._finding_row(run, item)
            for item in linked
        ]
        await self.findings.add_many(
            finding_rows,
            batch_size=self.batch_size,
        )
        await self._audit_findings(run, finding_rows)

        run.total_terms = result.total_terms
        run.matched_terms = result.matched_terms
        run.preferred_term_matches = result.preferred_term_matches
        run.forbidden_term_matches = result.forbidden_term_matches
        run.missing_required_translations = (
            result.missing_required_translations
        )
        run.inconsistent_terms = result.inconsistent_terms
        run.exception_applied_count = result.exception_applied_count
        run.total_findings = len(finding_rows)
        run.metrics_json = dict(result.metrics)
        run.warnings_json = list(result.warnings)
        run.status = (
            GlossaryValidationStatus.PARTIALLY_COMPLETED
            if result.warnings
            else GlossaryValidationStatus.COMPLETED
        )
        run.progress = 100
        run.current_stage = "Completed"
        run.completed_at = completed
        run.error_code = None
        run.error_message = None
        run.error_details_json = None
        document_file = await self.session.get(
            DocumentFile,
            run.document_file_id,
        )
        if document_file is not None:
            document_file.latest_glossary_validation_run_id = run.id
        await self.session.flush()
        return match_rows, finding_rows

    async def _previous_findings(
        self,
        run: GlossaryValidationRun,
    ) -> list[ValidationFinding]:
        previous_id = await self.session.scalar(
            select(GlossaryValidationRun.id)
            .where(
                GlossaryValidationRun.document_file_id
                == run.document_file_id,
                GlossaryValidationRun.id != run.id,
                GlossaryValidationRun.status.in_(
                    {
                        GlossaryValidationStatus.COMPLETED,
                        GlossaryValidationStatus.PARTIALLY_COMPLETED,
                    }
                ),
            )
            .order_by(
                desc(GlossaryValidationRun.completed_at),
                desc(GlossaryValidationRun.created_at),
            )
            .limit(1)
        )
        if previous_id is None:
            return []
        rows = await self.session.scalars(
            select(ValidationFinding).where(
                ValidationFinding.glossary_validation_run_id == previous_id
            )
        )
        return list(rows.all())

    @staticmethod
    def _finding_row(
        run: GlossaryValidationRun,
        signal: GlossaryFindingSignal,
    ) -> ValidationFinding:
        metrics = dict(signal.metrics)
        if signal.deduplication_key:
            metrics["deduplicationKey"] = signal.deduplication_key
        metrics.update(
            {
                "glossaryTermId": str(signal.glossary_term_id),
                "glossaryExceptionId": (
                    str(signal.exception_id)
                    if signal.exception_id is not None
                    else None
                ),
            }
        )
        return ValidationFinding(
            compliance_run_id=None,
            similarity_run_id=None,
            glossary_validation_run_id=run.id,
            document_id=run.document_id,
            document_revision_id=run.document_revision_id,
            document_file_id=run.document_file_id,
            validation_rule_id=None,
            finding_code=FindingCode(signal.finding_code),
            finding_type=FindingType.GLOSSARY,
            severity=FindingSeverity(signal.severity),
            status=FindingStatus.OPEN,
            title=signal.title,
            description=signal.description,
            recommendation=signal.recommendation,
            container_id=signal.container_id,
            detected_section_id=signal.detected_section_id,
            translation_group_id=signal.translation_group_id,
            extracted_block_id=signal.extracted_block_id,
            ocr_block_id=signal.ocr_block_id,
            source_reference=signal.source_reference,
            location_json={
                "glossaryTermId": str(signal.glossary_term_id),
                "exceptionId": (
                    str(signal.exception_id)
                    if signal.exception_id is not None
                    else None
                ),
            },
            language_code=signal.language_code,
            expected_value_json=None,
            actual_value_json={
                "matchedText": metrics.get("matchedText"),
            },
            metrics_json=metrics,
            is_system_generated=True,
            is_repeat=signal.is_repeat,
            previous_finding_id=signal.previous_finding_id,
            created_by=None,
        )

    async def _audit_findings(
        self,
        run: GlossaryValidationRun,
        findings: Sequence[ValidationFinding],
    ) -> None:
        for item in findings:
            await self.audit_logs.create(
                user_id=run.requested_by,
                action=AuditAction.CREATE_FINDING,
                entity_type="ValidationFinding",
                entity_id=item.id,
                description="Glossary validation finding generated.",
                new_values={
                    "glossaryValidationRunId": str(run.id),
                    "findingCode": item.finding_code.value,
                    "severity": item.severity.value,
                    "isRepeat": item.is_repeat,
                },
            )
