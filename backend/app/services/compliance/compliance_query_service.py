"""Department-scoped reads for retained Phase 8 compliance results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import ceil
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.compliance_enums import ComplianceStatus
from app.models.compliance_run import ComplianceRun
from app.models.detected_section import DetectedSection
from app.models.translation_group import TranslationGroup
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.detected_section_repository import (
    DetectedSectionRepository,
)
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.translation_group_repository import (
    TranslationGroupRepository,
)
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.schemas.compliance import (
    ComplianceComparisonResponse,
    ComplianceDocumentReference,
    ComplianceFileReference,
    ComplianceFindingSummary,
    ComplianceLanguageSummary,
    ComplianceRequesterReference,
    ComplianceRevisionReference,
    ComplianceRuleReference,
    ComplianceRunListResponse,
    ComplianceRunResponse,
    ComplianceScoreBreakdownResponse,
    ComplianceScoreComponent,
    ComplianceScorePenalties,
    ComplianceSummaryResponse,
    ComplianceTranslationGroupSummary,
    LanguageComplianceMetric,
)
from app.schemas.finding import FindingListItem, FindingListResponse
from app.schemas.section_detection import (
    DetectedSectionListResponse,
    DetectedSectionResponse,
    SectionLanguageResultResponse,
)
from app.schemas.translation_group import (
    TranslationGroupListResponse,
    TranslationGroupMemberResponse,
    TranslationGroupResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance._compat import first, json_safe
from app.services.compliance.compliance_comparison_service import (
    ComplianceComparisonService,
)
from app.services.compliance.compliance_export_service import (
    safe_source_reference,
)
from app.services.compliance.compliance_job_service import (
    compliance_run_not_found,
)
from app.services.documents.base import DocumentServiceBase, document_error


class ComplianceQueryService(DocumentServiceBase):
    """Read immutable runs and retained structural evidence."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.runs = ComplianceRunRepository(session)
        self.files = DocumentFileRepository(session)
        self.sections = cast(Any, DetectedSectionRepository(session))
        self.groups = TranslationGroupRepository(session)
        self.findings = ValidationFindingRepository(session)

    def _detected_section_repository(self) -> DetectedSectionRepository:
        return cast(DetectedSectionRepository, self.sections)

    async def get_run(self, run_id: UUID) -> ComplianceRunResponse:
        run = await self._run(run_id)
        return compliance_run_response(run)

    async def latest_for_file(
        self,
        file_id: UUID,
    ) -> ComplianceRunResponse:
        self._ensure_view()
        document_file = await self.files.get_by_id(file_id)
        if document_file is None or not self._can_access_department(
            document_file.document.department_id
        ):
            raise document_error(
                "The document file does not exist or is outside your scope.",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                status_code=404,
                title="Document file was not found.",
            )
        run = await self.runs.get_latest_for_file(
            file_id,
            department_ids=self._scope_department_ids(),
        )
        if run is None:
            raise compliance_run_not_found()
        return compliance_run_response(run)

    async def history_for_file(
        self,
        file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> ComplianceRunListResponse:
        self._ensure_view()
        document_file = await self.files.get_by_id(file_id)
        if document_file is None or not self._can_access_department(
            document_file.document.department_id
        ):
            raise document_error(
                "The document file does not exist or is outside your scope.",
                code="COMPLIANCE_SOURCE_NOT_AVAILABLE",
                status_code=404,
                title="Document file was not found.",
            )
        items, total = await self.runs.list_page(
            department_ids=self._scope_department_ids(),
            document_file_id=file_id,
            page=page,
            page_size=page_size,
        )
        return ComplianceRunListResponse(
            items=[compliance_run_response(run) for run in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def summary(
        self,
        run_id: UUID,
    ) -> ComplianceSummaryResponse:
        run = await self._run(run_id)
        validators = _mapping(run.metrics_json.get("validators"))
        presence_metrics = _validator_metrics(
            validators,
            "LANGUAGE_PRESENCE",
        )
        coverage_metrics = _validator_metrics(
            validators,
            "LANGUAGE_COVERAGE",
        )
        group_metrics = _validator_metrics(
            validators,
            "TRANSLATION_GROUPS",
        )
        required_metrics = _validator_metrics(
            validators,
            "REQUIRED_SECTIONS",
        )
        language_presence = {
            str(key): str(value)
            for key, value in _mapping(presence_metrics.get("presence")).items()
        }
        for language in run.required_languages_json:
            language_presence.setdefault(
                language,
                ("PRESENT" if language in _detected_languages(run) else "NOT_PRESENT"),
            )
        block_coverage = _float_mapping(coverage_metrics.get("blockCoverage"))
        character_coverage = _float_mapping(coverage_metrics.get("characterCoverage"))
        average_confidence = {
            str(key): (
                float(cast(Any, value)) if value is not None else None
            )
            for key, value in _mapping(
                presence_metrics.get("averageConfidence")
            ).items()
        }
        minimum_block_coverage = _float_mapping(
            run.rule_snapshot_json.get("minimumLanguageBlockCoverage")
        )
        minimum_character_coverage = _float_mapping(
            run.rule_snapshot_json.get("minimumLanguageCharacterCoverage")
        )
        finding_counts_by_language = await self.findings.count_by_language_for_run(
            run.id
        )
        (
            complete_groups,
            incomplete_groups,
        ) = await self.groups.count_completeness_for_run(run.id)
        total_groups = complete_groups + incomplete_groups
        low_confidence = int(
            cast(Any, group_metrics.get("lowConfidenceGroups", 0) or 0),
        )
        order_invalid = await self.groups.count_invalid_order_for_run(run.id)
        required_count = int(
            cast(
                Any,
                required_metrics.get(
                    "totalRequiredSections",
                    len(run.required_sections_json),
                )
                or 0,
            ),
        )
        complete_sections = int(
            cast(
                Any,
                required_metrics.get(
                    "completeSections",
                    max(
                        0,
                        required_count - len(run.missing_sections_json),
                    ),
                )
                or 0,
            ),
        )
        return ComplianceSummaryResponse(
            run_id=run.id,
            status=run.status,
            compliance_status=run.compliance_status,
            compliance_score=float(run.compliance_score),
            required_languages=list(run.required_languages_json),
            language_presence=language_presence,
            language_coverage={
                language: block_coverage.get(language, 0.0)
                for language in run.required_languages_json
            },
            language=ComplianceLanguageSummary(
                presence=language_presence,
                block_coverage=block_coverage,
                character_coverage=character_coverage,
                average_confidence=average_confidence,
            ),
            language_metrics=[
                LanguageComplianceMetric(
                    language_code=language,
                    presence=language_presence[language],
                    block_coverage=block_coverage.get(language, 0.0),
                    character_coverage=character_coverage.get(
                        language,
                        0.0,
                    ),
                    minimum_block_coverage=minimum_block_coverage.get(language),
                    minimum_character_coverage=(
                        minimum_character_coverage.get(language)
                    ),
                    average_confidence=average_confidence.get(language),
                    finding_count=finding_counts_by_language.get(
                        language,
                        0,
                    ),
                )
                for language in run.required_languages_json
            ],
            required_sections=required_count,
            detected_sections=_detected_section_count(run),
            complete_sections=complete_sections,
            translation_groups=ComplianceTranslationGroupSummary(
                total=total_groups,
                complete=complete_groups,
                incomplete=incomplete_groups,
                order_invalid=order_invalid,
                low_confidence=low_confidence,
            ),
            findings=ComplianceFindingSummary(
                total=run.total_findings,
                open=run.open_findings,
                critical=run.critical_findings,
                major=run.major_findings,
                minor=run.minor_findings,
                information=run.information_findings,
            ),
            warnings=cast(
                list[str] | list[dict[str, Any]],
                list(run.warnings_json),
            ),
        )

    async def score_breakdown(
        self,
        run_id: UUID,
    ) -> ComplianceScoreBreakdownResponse:
        run = await self._run(run_id)
        rule = run.rule_snapshot_json
        breakdown = _mapping(run.metrics_json.get("scoreBreakdown"))
        return ComplianceScoreBreakdownResponse(
            document_code=_component(
                run.document_code_score,
                _number(rule, "documentCodeWeight", 10),
            ),
            language_presence=_component(
                run.language_presence_score,
                _number(rule, "languagePresenceWeight", 25),
            ),
            language_coverage=_component(
                run.language_coverage_score,
                _number(rule, "languageCoverageWeight", 15),
            ),
            section_completeness=_component(
                run.section_completeness_score,
                _number(rule, "sectionCompletenessWeight", 20),
            ),
            language_order=_component(
                run.language_order_score,
                _number(rule, "languageOrderWeight", 10),
            ),
            translation_groups=_component(
                run.translation_group_score,
                _number(rule, "translationGroupWeight", 15),
            ),
            table_completeness=_component(
                run.table_completeness_score,
                _number(rule, "tableCompletenessWeight", 5),
            ),
            penalties=ComplianceScorePenalties(
                major=-abs(_number(breakdown, "majorPenalty", 0)),
                minor=-abs(_number(breakdown, "minorPenalty", 0)),
                other=0,
            ),
            weighted_score=_number(
                breakdown,
                "weightedScore",
                sum(
                    float(value)
                    for value in (
                        run.document_code_score,
                        run.language_presence_score,
                        run.language_coverage_score,
                        run.section_completeness_score,
                        run.language_order_score,
                        run.translation_group_score,
                        run.table_completeness_score,
                    )
                ),
            ),
            score_cap=(
                float(cast(Any, breakdown["scoreCap"]))
                if breakdown.get("scoreCap") is not None
                else None
            ),
            final_score=float(run.compliance_score),
        )

    async def list_sections(
        self,
        run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> DetectedSectionListResponse:
        await self._run(run_id)
        self._ensure_result_page_size(page_size)
        section_repository = self._detected_section_repository()
        total = await section_repository.count_for_run(run_id)
        language_result_total = (
            await section_repository.count_language_results_for_run_page(
                run_id,
                page=page,
                page_size=page_size,
            )
        )
        if language_result_total > self.settings.compliance_export_max_rows:
            raise document_error(
                ("Section-language results exceed the configured result row limit."),
                code="COMPLIANCE_RESULT_LANGUAGE_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance result page is too large.",
            )
        sections = await section_repository.list_for_run(
            run_id,
            page=page,
            page_size=page_size,
        )
        finding_counts = await self.findings.count_by_section_ids(
            [section.id for section in sections]
        )
        return DetectedSectionListResponse(
            items=[
                detected_section_response(
                    section,
                    finding_count=finding_counts.get(section.id, 0),
                )
                for section in sections
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_translation_groups(
        self,
        run_id: UUID,
        *,
        container_id: UUID | None = None,
        detected_section_id: UUID | None = None,
        is_complete: bool | None = None,
        is_order_valid: bool | None = None,
        low_confidence: bool | None = None,
        page: int = 1,
        page_size: int = 500,
    ) -> TranslationGroupListResponse:
        await self._run(run_id)
        self._ensure_result_page_size(
            page_size,
            maximum=self.settings.compliance_max_translation_groups,
        )
        confidence_threshold = self.settings.translation_group_min_confidence
        member_total = await self.groups.count_members_for_run_page(
            run_id,
            container_id=container_id,
            detected_section_id=detected_section_id,
            is_complete=is_complete,
            is_order_valid=is_order_valid,
            low_confidence=low_confidence,
            confidence_threshold=confidence_threshold,
            page=page,
            page_size=page_size,
        )
        if member_total > min(
            self.settings.compliance_max_blocks,
            self.settings.compliance_export_max_rows,
        ):
            raise document_error(
                ("Translation-group members exceed the configured result row limit."),
                code="COMPLIANCE_RESULT_MEMBER_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance result page is too large.",
            )
        groups, total = await self.groups.list_for_run(
            run_id,
            container_id=container_id,
            detected_section_id=detected_section_id,
            is_complete=is_complete,
            is_order_valid=is_order_valid,
            low_confidence=low_confidence,
            confidence_threshold=confidence_threshold,
            page=page,
            page_size=page_size,
        )
        finding_counts = await self.findings.count_by_translation_group_ids(
            [group.id for group in groups]
        )
        return TranslationGroupListResponse(
            items=[
                translation_group_response(
                    group,
                    finding_count=finding_counts.get(group.id, 0),
                )
                for group in groups
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def list_run_findings(
        self,
        run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> FindingListResponse:
        await self._run(run_id)
        self._ensure_result_page_size(page_size)
        total = await self.findings.count_for_run(run_id)
        findings = await self.findings.list_for_run(
            run_id,
            page=page,
            page_size=page_size,
        )
        return FindingListResponse(
            items=[compliance_finding_list_item(item) for item in findings],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=ceil(total / page_size) if total else 0,
        )

    async def compare(
        self,
        run_id: UUID,
        other_run_id: UUID,
    ) -> ComplianceComparisonResponse:
        current = await self._run(run_id)
        previous = await self._run(other_run_id)
        if current.document_id != previous.document_id:
            raise document_error(
                "Compliance comparison requires runs from the same document.",
                code="COMPLIANCE_COMPARISON_DOCUMENT_MISMATCH",
                title="Compliance runs cannot be compared.",
            )
        current_findings = await self._bounded_findings_for_comparison(current.id)
        previous_findings = await self._bounded_findings_for_comparison(previous.id)
        (
            previous_complete,
            previous_incomplete,
        ) = await self.groups.count_completeness_for_run(previous.id)
        (
            current_complete,
            current_incomplete,
        ) = await self.groups.count_completeness_for_run(current.id)
        result = ComplianceComparisonService().compare(
            {
                "compliance_score": previous.compliance_score,
                "compliance_status": previous.compliance_status,
                "detected_languages_json": (previous.detected_languages_json),
                "detected_sections_json": previous.detected_sections_json,
                "translation_groups": {
                    "total": previous_complete + previous_incomplete,
                    "complete": previous_complete,
                },
                "findings": previous_findings,
            },
            {
                "compliance_score": current.compliance_score,
                "compliance_status": current.compliance_status,
                "detected_languages_json": current.detected_languages_json,
                "detected_sections_json": current.detected_sections_json,
                "translation_groups": {
                    "total": current_complete + current_incomplete,
                    "complete": current_complete,
                },
                "findings": current_findings,
            },
        )
        return ComplianceComparisonResponse(
            current_run_id=current.id,
            previous_run_id=previous.id,
            score_change=result.score_change,
            previous_status=ComplianceStatus(result.previous_status),
            current_status=ComplianceStatus(result.current_status),
            languages_added=list(result.languages_added),
            languages_removed=list(result.languages_removed),
            sections_added=list(result.sections_added),
            sections_removed=list(result.sections_removed),
            new_findings=len(result.new_findings),
            resolved_candidates=len(result.not_reproduced_findings),
            repeated_findings=len(result.repeated_findings),
            translation_group_completeness_change=float(
                result.translation_group_complete_change
            ),
        )

    async def _bounded_findings_for_comparison(
        self,
        run_id: UUID,
    ) -> list[ValidationFinding]:
        maximum = self.settings.compliance_export_max_rows
        total = await self.findings.count_for_run(run_id)
        if total > maximum:
            raise document_error(
                "The compliance comparison exceeds the configured row limit.",
                code="COMPLIANCE_COMPARISON_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance results are too large to compare.",
            )
        if total == 0:
            return []
        return await self.findings.list_for_run(
            run_id,
            page=1,
            page_size=total,
        )

    def _ensure_result_page_size(
        self,
        page_size: int,
        *,
        maximum: int | None = None,
    ) -> None:
        configured_maximum = min(
            self.settings.compliance_export_max_rows,
            maximum or self.settings.compliance_export_max_rows,
        )
        if page_size > configured_maximum:
            raise document_error(
                "The requested page size exceeds the configured row limit.",
                field="pageSize",
                code="COMPLIANCE_RESULT_PAGE_LIMIT_EXCEEDED",
                status_code=413,
                title="Compliance result page is too large.",
            )

    async def _run(self, run_id: UUID) -> ComplianceRun:
        self._ensure_view()
        run = await self.runs.get_by_id(
            run_id,
            department_ids=self._scope_department_ids(),
        )
        if run is None:
            raise compliance_run_not_found()
        return run

    def _scope_department_ids(self) -> Sequence[UUID] | None:
        if self._view_all_departments:
            return None
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department assignment is required for compliance access."
            )
        return [self.user.department_id]

    @property
    def _view_all_departments(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
            is_superuser=self.user.is_superuser,
        )

    def _can_access_department(self, department_id: UUID) -> bool:
        return self._view_all_departments or (
            self.user.department_id is not None
            and self.user.department_id == department_id
        )

    def _ensure_view(self) -> None:
        if not has_permission(
            self.user.role,
            Permission.COMPLIANCE_VIEW,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError()


def compliance_run_response(run: ComplianceRun) -> ComplianceRunResponse:
    document = run.document
    revision = run.revision
    document_file = run.document_file
    rule = run.validation_rule
    requester = run.requester
    rule_snapshot = dict(run.rule_snapshot_json)
    snapshot_rule_code = _snapshot_text(rule_snapshot, "rule_code")
    snapshot_rule_name = _snapshot_text(rule_snapshot, "rule_name")
    snapshot_rule_version = _snapshot_integer(
        rule_snapshot,
        "rule_version",
    )
    return ComplianceRunResponse(
        id=run.id,
        compliance_job_id=run.compliance_job_id,
        document_id=run.document_id,
        document_revision_id=run.document_revision_id,
        document_file_id=run.document_file_id,
        extraction_run_id=run.extraction_run_id,
        ocr_run_id=run.ocr_run_id,
        language_detection_run_id=run.language_detection_run_id,
        validation_rule_id=run.validation_rule_id,
        document=ComplianceDocumentReference(
            id=document.id,
            base_document_code=document.base_document_code,
            title=document.title,
            department_id=document.department_id,
        ),
        revision=ComplianceRevisionReference(
            id=revision.id,
            revision_code=revision.revision_code,
            full_document_code=revision.full_document_code,
        ),
        file=ComplianceFileReference(
            id=document_file.id,
            filename=document_file.original_filename,
            file_extension=document_file.file_extension,
        ),
        validation_rule=ComplianceRuleReference(
            id=rule.id,
            code=snapshot_rule_code or rule.code,
            name=snapshot_rule_name or rule.name,
            version=snapshot_rule_version,
        ),
        rule_snapshot=rule_snapshot,
        source_content_hash=run.source_content_hash,
        status=run.status,
        compliance_status=run.compliance_status,
        compliance_score=float(run.compliance_score),
        maximum_score=float(run.maximum_score),
        document_code_score=float(run.document_code_score),
        language_presence_score=float(run.language_presence_score),
        language_coverage_score=float(run.language_coverage_score),
        section_completeness_score=float(run.section_completeness_score),
        language_order_score=float(run.language_order_score),
        translation_group_score=float(run.translation_group_score),
        table_completeness_score=float(run.table_completeness_score),
        total_findings=run.total_findings,
        critical_findings=run.critical_findings,
        major_findings=run.major_findings,
        minor_findings=run.minor_findings,
        information_findings=run.information_findings,
        open_findings=run.open_findings,
        required_languages=list(run.required_languages_json),
        detected_languages=run.detected_languages_json,
        missing_languages=list(run.missing_languages_json),
        required_sections=list(run.required_sections_json),
        detected_sections=run.detected_sections_json,
        missing_sections=list(run.missing_sections_json),
        warnings=cast(
            list[str] | list[dict[str, Any]],
            list(run.warnings_json),
        ),
        metrics=dict(run.metrics_json),
        started_at=run.started_at,
        completed_at=run.completed_at,
        requested_by=(
            ComplianceRequesterReference(id=requester.id, name=requester.name)
            if requester is not None
            else None
        ),
        created_at=run.created_at,
    )


def detected_section_response(
    section: DetectedSection,
    *,
    finding_count: int = 0,
) -> DetectedSectionResponse:
    return DetectedSectionResponse(
        id=section.id,
        compliance_run_id=section.compliance_run_id,
        section_definition_id=section.section_definition_id,
        canonical_code=section.canonical_code,
        container_id=section.container_id,
        start_block_id=section.start_block_id,
        end_block_id=section.end_block_id,
        heading_block_id=section.heading_block_id,
        heading_text=section.heading_text,
        heading_language_code=section.heading_language_code,
        match_type=section.match_type,
        match_confidence=float(section.match_confidence),
        section_order=section.section_order,
        is_required=section.is_required,
        is_complete=section.is_complete,
        language_presence=dict(section.language_presence_json),
        metrics=dict(section.metrics_json),
        language_results=[
            SectionLanguageResultResponse(
                id=result.id,
                detected_section_id=result.detected_section_id,
                language_code=result.language_code,
                presence_status=result.presence_status,
                block_count=result.block_count,
                character_count=result.character_count,
                coverage_percentage=float(result.coverage_percentage),
                average_confidence=(
                    float(result.average_confidence)
                    if result.average_confidence is not None
                    else None
                ),
                first_block_id=result.first_block_id,
                last_block_id=result.last_block_id,
                metrics=dict(result.metrics_json),
                created_at=result.created_at,
            )
            for result in section.language_results
        ],
        finding_count=finding_count,
        created_at=section.created_at,
    )


def translation_group_response(
    group: TranslationGroup,
    *,
    finding_count: int = 0,
) -> TranslationGroupResponse:
    return TranslationGroupResponse(
        id=group.id,
        compliance_run_id=group.compliance_run_id,
        container_id=group.container_id,
        detected_section_id=group.detected_section_id,
        group_index=group.group_index,
        group_type=group.group_type,
        start_block_order=group.start_block_order,
        end_block_order=group.end_block_order,
        source_reference=safe_source_reference(group.source_reference),
        expected_languages=list(group.expected_languages_json),
        detected_languages=list(group.detected_languages_json),
        language_order=list(group.language_order_json),
        is_complete=group.is_complete,
        is_order_valid=group.is_order_valid,
        confidence=float(group.confidence),
        metrics=_safe_public_mapping(group.metrics_json),
        members=[
            TranslationGroupMemberResponse(
                id=member.id,
                translation_group_id=member.translation_group_id,
                language_code=member.language_code,
                source_type=member.source_type,
                extracted_block_id=member.extracted_block_id,
                ocr_block_id=member.ocr_block_id,
                language_block_result_id=member.language_block_result_id,
                block_order=member.block_order,
                text_snapshot=member.text_snapshot,
                confidence=float(member.confidence),
                position=_safe_public_mapping(member.position_json),
                created_at=member.created_at,
            )
            for member in group.members
        ],
        finding_count=finding_count,
        created_at=group.created_at,
    )


def compliance_finding_list_item(
    finding: ValidationFinding,
) -> FindingListItem:
    """Map one run finding without exposing a filesystem source reference."""

    return FindingListItem(
        id=finding.id,
        compliance_run_id=finding.compliance_run_id,
        document_id=finding.document_id,
        document_revision_id=finding.document_revision_id,
        document_file_id=finding.document_file_id,
        finding_code=finding.finding_code,
        finding_type=finding.finding_type,
        severity=finding.severity,
        status=finding.status,
        title=finding.title,
        language_code=finding.language_code,
        detected_section_id=finding.detected_section_id,
        source_reference=(
            safe_source_reference(finding.source_reference)
            if finding.source_reference is not None
            else None
        ),
        page_number=finding.page_number,
        worksheet_name=finding.worksheet_name,
        cell_coordinate=finding.cell_coordinate,
        assigned_to=finding.assigned_to,
        is_system_generated=finding.is_system_generated,
        is_repeat=finding.is_repeat,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


def _safe_public_mapping(value: object) -> dict[str, object]:
    safe = json_safe(value)
    if not isinstance(safe, Mapping):
        return {}
    return {str(key): _safe_public_value(item) for key, item in safe.items()}


def _snapshot_text(snapshot: Mapping[str, object], name: str) -> str | None:
    value = first(snapshot, name, default=None)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _snapshot_integer(
    snapshot: Mapping[str, object],
    name: str,
) -> int | None:
    value = first(snapshot, name, default=None)
    if value is None:
        return None
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _safe_public_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _safe_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_public_value(item) for item in value]
    if isinstance(value, str):
        return safe_source_reference(value)
    return value


def _component(value: object, maximum: float) -> ComplianceScoreComponent:
    return ComplianceScoreComponent(
        earned=float(cast(Any, value)),
        maximum=maximum,
    )


def _mapping(value: object) -> dict[str, object]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, dict)
        else {}
    )


def _validator_metrics(
    validators: dict[str, object],
    code: str,
) -> dict[str, object]:
    return _mapping(_mapping(validators.get(code)).get("metrics"))


def _float_mapping(value: object) -> dict[str, float]:
    return {
        str(key): float(item)
        for key, item in _mapping(value).items()
        if isinstance(item, (int, float))
    }


def _number(
    values: dict[str, object],
    key: str,
    default: float,
) -> float:
    value = values.get(key, values.get(_camel_to_snake(key), default))
    return float(value) if isinstance(value, (int, float)) else default


def _camel_to_snake(value: str) -> str:
    output: list[str] = []
    for character in value:
        if character.isupper():
            output.extend(("_", character.lower()))
        else:
            output.append(character)
    return "".join(output)


def _detected_languages(run: ComplianceRun) -> list[str]:
    value = run.detected_languages_json
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(key) for key, item in value.items() if str(item).upper() == "PRESENT"]


def _detected_section_count(run: ComplianceRun) -> int:
    value = run.detected_sections_json
    return len(value)
