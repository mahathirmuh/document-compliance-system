"""Read-only reporting datasets separated from operational services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.models.compliance_run import ComplianceRun
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.glossary_enums import GlossaryValidationStatus
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.report_snapshot import AdvancedReportType
from app.models.revision_comparison import RevisionComparison
from app.models.similarity_enums import SimilarityRunStatus
from app.models.similarity_run import SimilarityRun
from app.models.validation_finding import ValidationFinding
from app.schemas.advanced_reporting import AdvancedReportFilters


@dataclass(frozen=True, slots=True)
class ReportDataset:
    report_type: AdvancedReportType
    summary: dict[str, object]
    data_series: list[dict[str, object]] = field(default_factory=list)
    tables: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ReportDatasetService:
    """Build bounded real datasets from retained application records."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        maximum_rows: int,
        maximum_chart_categories: int,
    ) -> None:
        self.session = session
        self.maximum_rows = maximum_rows
        self.maximum_chart_categories = maximum_chart_categories

    async def build(
        self,
        report_type: AdvancedReportType,
        filters: AdvancedReportFilters,
    ) -> ReportDataset:
        if report_type is AdvancedReportType.COMPLIANCE_OVERVIEW:
            return await self._compliance_overview(filters)
        if report_type is AdvancedReportType.FINDINGS_ANALYTICS:
            return await self._finding_analytics(filters)
        if report_type is AdvancedReportType.TRANSLATION_SIMILARITY:
            return await self._similarity(filters)
        if report_type is AdvancedReportType.GLOSSARY_COMPLIANCE:
            return await self._glossary(filters)
        if report_type is AdvancedReportType.REVISION_CHANGES:
            return await self._revision_changes(filters)
        if report_type in {
            AdvancedReportType.DEPARTMENT_PERFORMANCE,
            AdvancedReportType.DOCUMENT_TYPE_PERFORMANCE,
            AdvancedReportType.VALIDATION_RULE_PERFORMANCE,
        }:
            return await self._grouped_compliance(report_type, filters)
        if report_type is AdvancedReportType.LANGUAGE_QUALITY:
            return await self._language_quality(filters)
        return await self._processing_performance(filters)

    async def _compliance_overview(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._compliance_predicates(filters)
        runs = list(
            await self.session.scalars(
                select(ComplianceRun)
                .join(Document, Document.id == ComplianceRun.document_id)
                .join(
                    DocumentRevision,
                    DocumentRevision.id
                    == ComplianceRun.document_revision_id,
                )
                .where(*predicates)
                .order_by(ComplianceRun.created_at.desc())
                .limit(self.maximum_rows)
            )
        )
        scores = [float(item.compliance_score) for item in runs]
        status_counts: dict[str, int] = {}
        for item in runs:
            status_counts[item.compliance_status.value] = (
                status_counts.get(item.compliance_status.value, 0) + 1
            )
        critical = sum(item.critical_findings for item in runs)
        major = sum(item.major_findings for item in runs)
        summary: dict[str, object] = {
            "documentsValidated": len({item.document_id for item in runs}),
            "averageComplianceScore": (
                round(sum(scores) / len(scores), 2) if scores else None
            ),
            "medianComplianceScore": median(scores) if scores else None,
            "openCriticalFindings": critical,
            "openMajorFindings": major,
            **{
                self._camel_status(key): value
                for key, value in status_counts.items()
            },
        }
        rows: list[dict[str, object]] = [
            {
                "documentId": str(item.document_id),
                "revisionId": str(item.document_revision_id),
                "status": item.compliance_status.value,
                "score": float(item.compliance_score),
                "openFindings": item.open_findings,
                "createdAt": item.created_at.isoformat(),
            }
            for item in runs
        ]
        return ReportDataset(
            report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
            summary=summary,
            tables={"Compliance Runs": rows},
        )

    async def _finding_analytics(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._document_predicates(filters)
        predicates.extend(self._revision_predicates(filters))
        if filters.date_from:
            predicates.append(
                ValidationFinding.created_at
                >= self._date_start(filters.date_from)
            )
        if filters.date_to:
            predicates.append(
                ValidationFinding.created_at
                < self._date_after(filters.date_to)
            )
        if filters.finding_severities:
            predicates.append(
                ValidationFinding.severity.in_(filters.finding_severities)
            )
        if filters.finding_statuses:
            predicates.append(
                ValidationFinding.status.in_(filters.finding_statuses)
            )
        grouped = (
            select(
                ValidationFinding.finding_code,
                ValidationFinding.severity,
                ValidationFinding.status,
                func.count(ValidationFinding.id),
            )
            .join(Document, Document.id == ValidationFinding.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id
                == ValidationFinding.document_revision_id,
            )
            .where(*predicates)
            .group_by(
                ValidationFinding.finding_code,
                ValidationFinding.severity,
                ValidationFinding.status,
            )
            .limit(self.maximum_rows)
        )
        rows: list[dict[str, object]] = [
            {
                "findingCode": finding_code.value,
                "severity": severity.value,
                "status": status.value,
                "count": int(count),
            }
            for finding_code, severity, status, count in (
                await self.session.execute(grouped)
            ).all()
        ]
        return ReportDataset(
            report_type=AdvancedReportType.FINDINGS_ANALYTICS,
            summary={
                "totalFindings": sum(
                    int(cast(Any, item["count"])) for item in rows
                ),
                "categories": len(rows),
            },
            data_series=rows[: self.maximum_chart_categories],
            tables={"Finding Analytics": rows},
        )

    async def _similarity(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._document_predicates(filters)
        predicates.extend(self._revision_predicates(filters))
        predicates.extend(
            [
                SimilarityRun.status.in_(
                    (
                        SimilarityRunStatus.COMPLETED,
                        SimilarityRunStatus.PARTIALLY_COMPLETED,
                    )
                ),
                *self._date_predicates(SimilarityRun.created_at, filters),
            ]
        )
        if filters.validation_rule_ids:
            predicates.append(
                ComplianceRun.validation_rule_id.in_(
                    filters.validation_rule_ids
                )
            )
        rows = list(
            await self.session.scalars(
                select(SimilarityRun)
                .join(Document, Document.id == SimilarityRun.document_id)
                .join(
                    DocumentRevision,
                    DocumentRevision.id
                    == SimilarityRun.document_revision_id,
                )
                .join(
                    ComplianceRun,
                    ComplianceRun.id == SimilarityRun.compliance_run_id,
                )
                .where(*predicates)
                .order_by(SimilarityRun.created_at.desc())
                .limit(self.maximum_rows)
            )
        )
        averages = self._numbers(rows, "average_similarity")
        id_en_averages = self._numbers(
            rows, "id_en_average_similarity"
        )
        id_zh_averages = self._numbers(
            rows, "id_zh_average_similarity"
        )
        en_zh_averages = self._numbers(
            rows, "en_zh_average_similarity"
        )
        summary: dict[str, object] = {
            "status": "AVAILABLE" if rows else "NOT_EVALUATED",
            "runs": len(rows),
            "averageSimilarity": self._mean(averages),
            "medianSimilarity": median(averages) if averages else None,
            "lowSimilarityGroups": sum(
                item.low_similarity_groups for item in rows
            ),
            "needsReviewGroups": sum(
                item.review_similarity_groups for item in rows
            ),
            "idEnAverageSimilarity": self._mean(id_en_averages),
            "idZhAverageSimilarity": self._mean(id_zh_averages),
            "enZhAverageSimilarity": self._mean(en_zh_averages),
            "numberMismatches": sum(
                item.number_mismatch_count for item in rows
            ),
            "dateMismatches": sum(item.date_mismatch_count for item in rows),
            "measurementMismatches": sum(
                item.measurement_mismatch_count for item in rows
            ),
            "referenceMismatches": sum(
                item.reference_mismatch_count for item in rows
            ),
            "negationMismatches": sum(
                item.negation_mismatch_count for item in rows
            ),
        }
        table: list[dict[str, object]] = [
            {
                "runId": str(item.id),
                "documentId": str(item.document_id),
                "status": item.status.value,
                "averageSimilarity": self._number(
                    item.average_similarity
                ),
                "minimumSimilarity": self._number(
                    item.minimum_similarity
                ),
                "idEnAverageSimilarity": self._number(
                    item.id_en_average_similarity
                ),
                "idZhAverageSimilarity": self._number(
                    item.id_zh_average_similarity
                ),
                "enZhAverageSimilarity": self._number(
                    item.en_zh_average_similarity
                ),
                "lowSimilarityGroups": item.low_similarity_groups,
                "needsReviewGroups": item.review_similarity_groups,
                "numberMismatches": item.number_mismatch_count,
                "dateMismatches": item.date_mismatch_count,
                "measurementMismatches": (
                    item.measurement_mismatch_count
                ),
                "referenceMismatches": item.reference_mismatch_count,
                "negationMismatches": item.negation_mismatch_count,
                "createdAt": item.created_at.isoformat(),
            }
            for item in rows
        ]
        return ReportDataset(
            report_type=AdvancedReportType.TRANSLATION_SIMILARITY,
            summary=summary,
            tables={"Translation Similarity": table},
            warnings=(
                []
                if rows
                else ["No compatible similarity runs are available."]
            ),
        )

    async def _glossary(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._document_predicates(filters)
        predicates.extend(self._revision_predicates(filters))
        predicates.extend(
            [
                GlossaryValidationRun.status.in_(
                    (
                        GlossaryValidationStatus.COMPLETED,
                        GlossaryValidationStatus.PARTIALLY_COMPLETED,
                    )
                ),
                *self._date_predicates(
                    GlossaryValidationRun.created_at, filters
                ),
            ]
        )
        if filters.validation_rule_ids:
            predicates.append(
                ComplianceRun.validation_rule_id.in_(
                    filters.validation_rule_ids
                )
            )
        rows = list(
            await self.session.scalars(
                select(GlossaryValidationRun)
                .join(
                    Document,
                    Document.id == GlossaryValidationRun.document_id,
                )
                .join(
                    DocumentRevision,
                    DocumentRevision.id
                    == GlossaryValidationRun.document_revision_id,
                )
                .outerjoin(
                    ComplianceRun,
                    ComplianceRun.id
                    == GlossaryValidationRun.compliance_run_id,
                )
                .where(*predicates)
                .order_by(GlossaryValidationRun.created_at.desc())
                .limit(self.maximum_rows)
            )
        )
        preferred = sum(item.preferred_term_matches for item in rows)
        matched = sum(item.matched_terms for item in rows)
        summary: dict[str, object] = {
            "status": "AVAILABLE" if rows else "NOT_EVALUATED",
            "runs": len(rows),
            "preferredMatches": preferred,
            "preferredTermCompliance": (
                round(preferred / matched * 100, 2) if matched else None
            ),
            "forbiddenMatches": sum(
                item.forbidden_term_matches for item in rows
            ),
            "missingRequiredTranslations": sum(
                item.missing_required_translations for item in rows
            ),
            "inconsistentTranslations": sum(
                item.inconsistent_terms for item in rows
            ),
            "exceptionsApplied": sum(
                item.exception_applied_count for item in rows
            ),
            "totalFindings": sum(item.total_findings for item in rows),
        }
        return ReportDataset(
            report_type=AdvancedReportType.GLOSSARY_COMPLIANCE,
            summary=summary,
            tables={
                "Glossary Compliance": [
                    {
                        "runId": str(item.id),
                        "documentId": str(item.document_id),
                        "status": item.status.value,
                        "preferredMatches": item.preferred_term_matches,
                        "forbiddenMatches": item.forbidden_term_matches,
                        "missingRequiredTranslations": (
                            item.missing_required_translations
                        ),
                        "inconsistentTranslations": (
                            item.inconsistent_terms
                        ),
                        "exceptionsApplied": item.exception_applied_count,
                        "totalFindings": item.total_findings,
                        "createdAt": item.created_at.isoformat(),
                    }
                    for item in rows
                ]
            },
            warnings=(
                []
                if rows
                else [
                    "No compatible glossary validation runs are available."
                ]
            ),
        )

    async def _revision_changes(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._document_predicates(filters)
        predicates.extend(self._revision_predicates(filters))
        predicates.extend(
            self._date_predicates(RevisionComparison.created_at, filters)
        )
        rows = list(
            await self.session.scalars(
                select(RevisionComparison)
                .join(Document, Document.id == RevisionComparison.document_id)
                .join(
                    DocumentRevision,
                    DocumentRevision.id
                    == RevisionComparison.target_revision_id,
                )
                .where(*predicates)
                .order_by(RevisionComparison.created_at.desc())
                .limit(self.maximum_rows)
            )
        )
        return ReportDataset(
            report_type=AdvancedReportType.REVISION_CHANGES,
            summary={
                "comparisons": len(rows),
                "totalChanges": sum(item.total_changes for item in rows),
                "added": sum(item.added_blocks for item in rows),
                "removed": sum(item.removed_blocks for item in rows),
                "modified": sum(item.modified_blocks for item in rows),
                "improved": sum(
                    item.classification.value == "IMPROVED" for item in rows
                ),
                "regressed": sum(
                    item.classification.value == "REGRESSED" for item in rows
                ),
            },
            tables={
                "Revision Changes": [
                    {
                        "comparisonId": str(item.id),
                        "documentId": str(item.document_id),
                        "classification": item.classification.value,
                        "totalChanges": item.total_changes,
                        "added": item.added_blocks,
                        "removed": item.removed_blocks,
                        "modified": item.modified_blocks,
                    }
                    for item in rows
                ]
            },
        )

    async def _grouped_compliance(
        self,
        report_type: AdvancedReportType,
        filters: AdvancedReportFilters,
    ) -> ReportDataset:
        predicates = self._compliance_predicates(filters)
        group_column = {
            AdvancedReportType.DEPARTMENT_PERFORMANCE: Document.department_id,
            AdvancedReportType.DOCUMENT_TYPE_PERFORMANCE: (
                Document.document_type_id
            ),
            AdvancedReportType.VALIDATION_RULE_PERFORMANCE: (
                ComplianceRun.validation_rule_id
            ),
        }[report_type]
        statement = (
            select(
                group_column,
                func.count(ComplianceRun.id),
                func.avg(ComplianceRun.compliance_score),
                func.sum(ComplianceRun.open_findings),
                func.sum(ComplianceRun.critical_findings),
            )
            .join(Document, Document.id == ComplianceRun.document_id)
            .join(
                DocumentRevision,
                DocumentRevision.id
                == ComplianceRun.document_revision_id,
            )
            .where(*predicates)
            .group_by(group_column)
            .limit(self.maximum_chart_categories)
        )
        rows: list[dict[str, object]] = [
            {
                "groupId": str(group_id),
                "validatedDocumentCount": int(count),
                "averageComplianceScore": float(average or 0),
                "openFindings": int(open_findings or 0),
                "criticalFindings": int(critical or 0),
            }
            for group_id, count, average, open_findings, critical in (
                await self.session.execute(statement)
            ).all()
        ]
        return ReportDataset(
            report_type=report_type,
            summary={"groups": len(rows)},
            data_series=rows,
            tables={"Document Compliance Performance": rows},
        )

    async def _language_quality(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        overview = await self._compliance_overview(filters)
        return ReportDataset(
            report_type=AdvancedReportType.LANGUAGE_QUALITY,
            summary={
                "documentsValidated": overview.summary.get(
                    "documentsValidated", 0
                ),
                "note": (
                    "Language quality combines retained structural coverage "
                    "with available similarity signals."
                ),
            },
            tables=overview.tables,
            warnings=[
                "Similarity is a review signal and is not legal proof."
            ],
        )

    async def _processing_performance(
        self, filters: AdvancedReportFilters
    ) -> ReportDataset:
        predicates = self._document_predicates(filters)
        statement = select(func.count(Document.id))
        if filters.document_status_ids:
            statement = statement.join(
                DocumentRevision,
                DocumentRevision.id == Document.current_revision_id,
            )
            predicates.extend(self._revision_predicates(filters))
        document_count_value = await self.session.scalar(
            statement.where(*predicates)
        )
        document_count = int(document_count_value or 0)
        return ReportDataset(
            report_type=AdvancedReportType.PROCESSING_PERFORMANCE,
            summary={
                "documentCount": document_count,
                "reportScope": "Document processing jobs",
            },
            warnings=[
                (
                    "Detailed queue duration metrics require completed job "
                    "timestamps for each processing stage."
                )
            ],
        )

    def _compliance_predicates(
        self, filters: AdvancedReportFilters
    ) -> list[ColumnElement[bool]]:
        predicates = self._document_predicates(filters)
        predicates.extend(self._revision_predicates(filters))
        if filters.validation_rule_ids:
            predicates.append(
                ComplianceRun.validation_rule_id.in_(
                    filters.validation_rule_ids
                )
            )
        if filters.compliance_statuses:
            predicates.append(
                ComplianceRun.compliance_status.in_(
                    filters.compliance_statuses
                )
            )
        if filters.date_from:
            predicates.append(
                ComplianceRun.created_at >= self._date_start(filters.date_from)
            )
        if filters.date_to:
            predicates.append(
                ComplianceRun.created_at < self._date_after(filters.date_to)
            )
        return predicates

    @staticmethod
    def _document_predicates(
        filters: AdvancedReportFilters,
    ) -> list[ColumnElement[bool]]:
        predicates: list[ColumnElement[bool]] = []
        if filters.department_ids:
            predicates.append(
                Document.department_id.in_(filters.department_ids)
            )
        if filters.section_ids:
            predicates.append(Document.section_id.in_(filters.section_ids))
        if filters.document_type_ids:
            predicates.append(
                Document.document_type_id.in_(filters.document_type_ids)
            )
        if not filters.include_archived:
            predicates.append(Document.is_archived.is_(False))
        return predicates

    @staticmethod
    def _revision_predicates(
        filters: AdvancedReportFilters,
    ) -> list[ColumnElement[bool]]:
        if not filters.document_status_ids:
            return []
        return [
            DocumentRevision.document_status_id.in_(
                filters.document_status_ids
            )
        ]

    @classmethod
    def _date_predicates(
        cls,
        column: InstrumentedAttribute[datetime],
        filters: AdvancedReportFilters,
    ) -> list[ColumnElement[bool]]:
        predicates: list[ColumnElement[bool]] = []
        if filters.date_from:
            predicates.append(column >= cls._date_start(filters.date_from))
        if filters.date_to:
            predicates.append(column < cls._date_after(filters.date_to))
        return predicates

    @staticmethod
    def _not_evaluated(
        report_type: AdvancedReportType, warning: str
    ) -> ReportDataset:
        return ReportDataset(
            report_type=report_type,
            summary={"status": "NOT_EVALUATED"},
            warnings=[warning],
        )

    @staticmethod
    def _date_start(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    @staticmethod
    def _date_after(value: date) -> datetime:
        return datetime.combine(
            value + timedelta(days=1), time.min, tzinfo=UTC
        )

    @staticmethod
    def _camel_status(value: str) -> str:
        parts = value.lower().split("_")
        return parts[0] + "".join(part.title() for part in parts[1:])

    @staticmethod
    def _number(value: object | None) -> float | None:
        return float(cast(Any, value)) if value is not None else None

    @classmethod
    def _numbers(
        cls,
        rows: Sequence[object],
        attribute: str,
    ) -> list[float]:
        return [
            number
            for item in rows
            if (number := cls._number(getattr(item, attribute, None)))
            is not None
        ]

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None
