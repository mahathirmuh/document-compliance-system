"""Build canonical revision contexts from retained local processing runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_enums import FindingSeverity, FindingStatus
from app.models.compliance_run import ComplianceRun
from app.models.detected_section import DetectedSection
from app.models.document_file import DocumentFile
from app.models.extracted_block import ExtractedBlock
from app.models.extracted_container import ExtractedContainer
from app.models.extraction_run import ExtractionRun
from app.models.glossary_enums import GlossaryValidationStatus
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.language_block_result import LanguageBlockResult
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.similarity_enums import SimilarityRunStatus
from app.models.similarity_run import SimilarityRun
from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.models.validation_finding import ValidationFinding
from app.services.revision_comparison.revision_alignment_service import (
    CanonicalRevisionItem,
)


class RevisionContextError(ValueError):
    """A prerequisite is missing or incompatible."""


@dataclass(frozen=True, slots=True)
class RevisionContext:
    document_file_id: UUID
    document_revision_id: UUID
    extraction_run_id: UUID
    compliance_run_id: UUID | None
    similarity_run_id: UUID | None
    glossary_run_id: UUID | None
    content_hash: str
    items: list[CanonicalRevisionItem]
    language_counts: dict[str, int]
    compliance_score: float | None
    compliance_status: str | None
    findings: list[dict[str, object]]
    similarity_score: float | None = None
    glossary_violation_count: int | None = None
    open_finding_count: int = 0
    critical_open_finding_count: int = 0
    language_coverage: dict[str, float] | None = None
    language_coverage_basis: str | None = None


class RevisionContextService:
    """Read only retained database content; never open or mutate binaries."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        maximum_blocks: int = 200_000,
    ) -> None:
        self.session = session
        self.maximum_blocks = maximum_blocks

    async def build(self, document_file: DocumentFile) -> RevisionContext:
        extraction_id = document_file.latest_extraction_run_id
        if extraction_id is None:
            raise RevisionContextError(
                "Run document extraction before comparing this revision."
            )
        extraction = await self.session.get(ExtractionRun, extraction_id)
        if (
            extraction is None
            or extraction.document_file_id != document_file.id
            or extraction.document_id != document_file.document_id
            or extraction.document_revision_id
            != document_file.document_revision_id
        ):
            raise RevisionContextError(
                "The latest extraction run is unavailable or incompatible."
            )
        if extraction.total_blocks > self.maximum_blocks:
            raise RevisionContextError(
                "The revision exceeds the configured comparison block limit."
            )

        compliance: ComplianceRun | None = None
        if document_file.latest_compliance_run_id is not None:
            compliance = await self.session.get(
                ComplianceRun, document_file.latest_compliance_run_id
            )
            if (
                compliance is not None
                and (
                    compliance.document_file_id != document_file.id
                    or compliance.document_id != document_file.document_id
                    or compliance.document_revision_id
                    != document_file.document_revision_id
                )
            ):
                compliance = None

        similarity = await self._similarity_run(document_file)
        glossary = await self._glossary_run(document_file)

        group_metadata = await self._group_metadata(
            compliance.id if compliance else None
        )
        (
            language_metadata,
            language_coverage,
            language_coverage_basis,
        ) = await self._language_metadata(document_file)
        statement = (
            select(ExtractedBlock, ExtractedContainer)
            .join(
                ExtractedContainer,
                ExtractedContainer.id == ExtractedBlock.container_id,
            )
            .where(ExtractedBlock.extraction_run_id == extraction.id)
            .order_by(
                ExtractedContainer.container_index.asc(),
                ExtractedBlock.block_order.asc(),
                ExtractedBlock.id.asc(),
            )
            .limit(self.maximum_blocks + 1)
        )
        rows = list((await self.session.execute(statement)).all())
        if len(rows) > self.maximum_blocks:
            raise RevisionContextError(
                "The revision exceeds the configured comparison block limit."
            )
        items: list[CanonicalRevisionItem] = []
        language_counts: Counter[str] = Counter()
        for absolute_order, (block, container) in enumerate(rows):
            group = group_metadata.get(block.id, {})
            language = str(
                group.get("languageCode")
                or language_metadata.get(block.id)
                or "unknown"
            )
            language_counts[language] += 1
            items.append(
                CanonicalRevisionItem(
                    id=block.id,
                    text=block.text,
                    order=absolute_order,
                    entity_type=block.block_type.value,
                    language_code=language,
                    source_reference=block.source_reference,
                    container_id=block.container_id,
                    container_identity=(
                        container.name
                        or container.title
                        or (
                            f"{container.container_type.value}:"
                            f"{container.container_index}"
                        )
                    ),
                    section_id=self._uuid_value(group.get("sectionId")),
                    section_code=self._text_value(
                        group.get("sectionCode")
                    ),
                    translation_group_id=self._uuid_value(
                        group.get("translationGroupId")
                    ),
                    translation_group_type=self._text_value(
                        group.get("translationGroupType")
                    ),
                    metadata={
                        "blockType": block.block_type.value,
                        "containerIndex": container.container_index,
                        "headingLevel": block.heading_level,
                    },
                )
            )

        findings = await self._findings(
            compliance_run_id=compliance.id if compliance else None,
            similarity_run_id=similarity.id if similarity else None,
            glossary_run_id=glossary.id if glossary else None,
        )
        open_statuses = {
            FindingStatus.OPEN.value,
            FindingStatus.IN_REVIEW.value,
            FindingStatus.REOPENED.value,
        }
        open_findings = [
            item
            for item in findings
            if item.get("status") in open_statuses
        ]
        return RevisionContext(
            document_file_id=document_file.id,
            document_revision_id=document_file.document_revision_id,
            extraction_run_id=extraction.id,
            compliance_run_id=compliance.id if compliance else None,
            similarity_run_id=similarity.id if similarity else None,
            glossary_run_id=glossary.id if glossary else None,
            content_hash=(
                extraction.content_hash
                or extraction.source_sha256_hash
                or document_file.sha256_hash
            ),
            items=items,
            language_counts=dict(language_counts),
            compliance_score=(
                float(compliance.compliance_score)
                if compliance is not None
                else None
            ),
            compliance_status=(
                compliance.compliance_status.value
                if compliance is not None
                else None
            ),
            findings=findings,
            similarity_score=(
                float(similarity.average_similarity)
                if similarity is not None
                and similarity.average_similarity is not None
                else None
            ),
            glossary_violation_count=(
                glossary.total_findings if glossary is not None else None
            ),
            open_finding_count=len(open_findings),
            critical_open_finding_count=sum(
                item.get("severity") == FindingSeverity.CRITICAL.value
                for item in open_findings
            ),
            language_coverage=language_coverage,
            language_coverage_basis=language_coverage_basis,
        )

    async def _group_metadata(
        self, compliance_run_id: UUID | None
    ) -> dict[UUID, dict[str, object]]:
        if compliance_run_id is None:
            return {}
        statement = (
            select(
                TranslationGroupMember.extracted_block_id,
                TranslationGroupMember.language_code,
                TranslationGroup.id,
                TranslationGroup.group_type,
                DetectedSection.id,
                DetectedSection.canonical_code,
            )
            .join(
                TranslationGroup,
                TranslationGroup.id
                == TranslationGroupMember.translation_group_id,
            )
            .outerjoin(
                DetectedSection,
                DetectedSection.id == TranslationGroup.detected_section_id,
            )
            .where(
                TranslationGroup.compliance_run_id == compliance_run_id,
                TranslationGroupMember.extracted_block_id.is_not(None),
            )
        )
        output: dict[UUID, dict[str, object]] = {}
        for row in (await self.session.execute(statement)).all():
            block_id = row[0]
            if block_id is None:
                continue
            output[block_id] = {
                "languageCode": row[1],
                "translationGroupId": row[2],
                "translationGroupType": row[3].value,
                "sectionId": row[4],
                "sectionCode": row[5],
            }
        return output

    async def _language_metadata(
        self, document_file: DocumentFile
    ) -> tuple[dict[UUID, str], dict[str, float] | None, str | None]:
        run_id = document_file.latest_language_detection_run_id
        if run_id is None:
            return {}, None, None
        run = await self.session.get(LanguageDetectionRun, run_id)
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.document_id != document_file.document_id
            or run.document_revision_id
            != document_file.document_revision_id
            or run.status
            not in {
                LanguageDetectionRunStatus.COMPLETED,
                LanguageDetectionRunStatus.PARTIALLY_COMPLETED,
            }
        ):
            return {}, None, None
        rows = await self.session.execute(
            select(
                LanguageBlockResult.extracted_block_id,
                LanguageBlockResult.language_code,
            ).where(
                LanguageBlockResult.language_detection_run_id == run.id,
                LanguageBlockResult.extracted_block_id.is_not(None),
            )
        )
        languages = {
            block_id: language.value
            for block_id, language in rows.all()
            if block_id is not None
        }
        coverage, basis = self._retained_language_coverage(run)
        return languages, coverage, basis

    @staticmethod
    def _retained_language_coverage(
        run: LanguageDetectionRun,
    ) -> tuple[dict[str, float] | None, str | None]:
        """Use persisted Phase 7 coverage; never infer it from raw counts."""

        metadata = run.metadata_json or {}
        raw_coverage = metadata.get("coverage")
        if not isinstance(raw_coverage, dict):
            return None, None
        for key in ("characterCoverage", "blockCoverage"):
            values = raw_coverage.get(key)
            if not isinstance(values, dict):
                continue
            output: dict[str, float] = {}
            for language in ("id", "en", "zh"):
                value = values.get(language)
                if not isinstance(value, (int, float)):
                    continue
                numeric = float(value)
                if 0 <= numeric <= 100:
                    output[language] = numeric
            if output:
                return output, key
        return None, None

    async def _findings(
        self,
        *,
        compliance_run_id: UUID | None,
        similarity_run_id: UUID | None,
        glossary_run_id: UUID | None,
    ) -> list[dict[str, object]]:
        source_predicates = [
            predicate
            for predicate in (
                (
                    ValidationFinding.compliance_run_id
                    == compliance_run_id
                    if compliance_run_id is not None
                    else None
                ),
                (
                    ValidationFinding.similarity_run_id
                    == similarity_run_id
                    if similarity_run_id is not None
                    else None
                ),
                (
                    ValidationFinding.glossary_validation_run_id
                    == glossary_run_id
                    if glossary_run_id is not None
                    else None
                ),
            )
            if predicate is not None
        ]
        if not source_predicates:
            return []
        rows = list(
            await self.session.scalars(
                select(ValidationFinding)
                .where(or_(*source_predicates))
                .order_by(
                    ValidationFinding.created_at.asc(),
                    ValidationFinding.id.asc(),
                )
            )
        )
        return [
            {
                "id": str(item.id),
                "deduplicationKey": (
                    f"{item.finding_code.value}|"
                    f"{item.detected_section_id or ''}|"
                    f"{item.language_code or ''}|"
                    f"{item.source_reference or ''}"
                ),
                "findingCode": item.finding_code.value,
                "severity": item.severity.value,
                "status": item.status.value,
                "section": (
                    str(item.detected_section_id)
                    if item.detected_section_id
                    else None
                ),
                "languageCode": item.language_code,
                "sourceReference": item.source_reference,
            }
            for item in rows
        ]

    async def _similarity_run(
        self, document_file: DocumentFile
    ) -> SimilarityRun | None:
        run_id = getattr(document_file, "latest_similarity_run_id", None)
        if run_id is None:
            return None
        run = await self.session.get(SimilarityRun, run_id)
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.document_id != document_file.document_id
            or run.document_revision_id
            != document_file.document_revision_id
            or run.status
            not in {
                SimilarityRunStatus.COMPLETED,
                SimilarityRunStatus.PARTIALLY_COMPLETED,
            }
        ):
            return None
        return run

    async def _glossary_run(
        self, document_file: DocumentFile
    ) -> GlossaryValidationRun | None:
        run_id = getattr(
            document_file, "latest_glossary_validation_run_id", None
        )
        if run_id is None:
            return None
        run = await self.session.get(GlossaryValidationRun, run_id)
        if (
            run is None
            or run.document_file_id != document_file.id
            or run.document_id != document_file.document_id
            or run.document_revision_id
            != document_file.document_revision_id
            or run.status
            not in {
                GlossaryValidationStatus.COMPLETED,
                GlossaryValidationStatus.PARTIALLY_COMPLETED,
            }
        ):
            return None
        return run

    @staticmethod
    def _uuid_value(value: object) -> UUID | None:
        return value if isinstance(value, UUID) else None

    @staticmethod
    def _text_value(value: object) -> str | None:
        return str(value) if value is not None else None
