"""Atomic persistence for one completed similarity pipeline."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.finding_occurrence import FindingOccurrence
from app.models.similarity_enums import (
    SimilarityJobStatus,
    SimilarityRunStatus,
)
from app.models.similarity_job import SimilarityJob
from app.models.similarity_result import TranslationSimilarityResult
from app.models.similarity_run import SimilarityRun
from app.models.similarity_section_summary import SectionSimilaritySummary
from app.models.validation_finding import ValidationFinding
from app.repositories.section_similarity_repository import (
    SectionSimilarityRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.repositories.translation_similarity_repository import (
    TranslationSimilarityRepository,
)
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.schemas.similarity_internal import SimilarityPipelineResult
from app.services.quality_score_service import QualityScoreService
from app.utils.datetime import utc_now


class SimilarityPersistenceService:
    def __init__(self, session: AsyncSession, settings: object) -> None:
        self.session = session
        self.batch_size = int(
            getattr(settings, "similarity_db_batch_size", 500)
        )
        self.runs = SimilarityRunRepository(session)
        self.results = TranslationSimilarityRepository(session)
        self.sections = SectionSimilarityRepository(session)
        self.findings = ValidationFindingRepository(session)

    async def persist(
        self,
        job: SimilarityJob,
        pipeline: SimilarityPipelineResult,
    ) -> SimilarityRun:
        completed = utc_now()
        aggregate = pipeline.aggregate
        provider = pipeline.provider_info
        warnings = list(dict.fromkeys(pipeline.warnings))
        quality = QualityScoreService.translation_quality(
            aggregate.average_similarity
        )
        run = SimilarityRun(
            similarity_job_id=job.id,
            document_id=job.document_id,
            document_revision_id=job.document_revision_id,
            document_file_id=job.document_file_id,
            compliance_run_id=job.compliance_run_id,
            language_detection_run_id=job.language_detection_run_id,
            provider=str(provider.get("provider") or job.provider),
            model_name=str(provider.get("modelName") or job.model_name),
            model_version=(
                str(provider["modelVersion"])
                if provider.get("modelVersion") is not None
                else None
            ),
            status=aggregate.status,
            source_content_hash=pipeline.context.source_content_hash,
            translation_group_count=aggregate.translation_group_count,
            eligible_group_count=aggregate.eligible_group_count,
            analysed_group_count=aggregate.analysed_group_count,
            skipped_group_count=aggregate.skipped_group_count,
            failed_group_count=aggregate.failed_group_count,
            average_similarity=_decimal_or_none(
                aggregate.average_similarity
            ),
            minimum_similarity=_decimal_or_none(
                aggregate.minimum_similarity
            ),
            maximum_similarity=_decimal_or_none(
                aggregate.maximum_similarity
            ),
            id_en_average_similarity=_decimal_or_none(
                aggregate.pair_averages.get("id-en")
            ),
            id_zh_average_similarity=_decimal_or_none(
                aggregate.pair_averages.get("id-zh")
            ),
            en_zh_average_similarity=_decimal_or_none(
                aggregate.pair_averages.get("en-zh")
            ),
            high_similarity_groups=aggregate.high_similarity_groups,
            review_similarity_groups=aggregate.review_similarity_groups,
            low_similarity_groups=aggregate.low_similarity_groups,
            unavailable_similarity_groups=(
                aggregate.unavailable_similarity_groups
            ),
            number_mismatch_count=aggregate.mismatch_counts.get("number", 0),
            date_mismatch_count=aggregate.mismatch_counts.get("date", 0),
            measurement_mismatch_count=aggregate.mismatch_counts.get(
                "measurement", 0
            ),
            reference_mismatch_count=aggregate.mismatch_counts.get(
                "reference", 0
            ),
            negation_mismatch_count=aggregate.mismatch_counts.get(
                "negation", 0
            ),
            warnings_json=warnings,
            metrics_json={
                **aggregate.metrics,
                "provider": provider,
                "findingDraftCount": len(pipeline.findings),
                "translationQualityScore": quality.score,
                "translationQualityStatus": quality.status.value,
                "qualityConfigurationSnapshot": (
                    pipeline.context.quality_configuration
                ),
            },
            started_at=job.started_at or completed,
            completed_at=completed,
            requested_by=job.requested_by,
        )
        await self.runs.add(run)
        models = [
            TranslationSimilarityResult(
                similarity_run_id=run.id,
                translation_group_id=item.translation_group_id,
                detected_section_id=item.detected_section_id,
                container_id=item.container_id,
                source_reference=item.source_reference[:1000],
                source_language_code=item.source_language_code,
                target_language_code=item.target_language_code,
                source_member_id=item.source_member_id,
                target_member_id=item.target_member_id,
                source_text_hash=item.source_text_hash,
                target_text_hash=item.target_text_hash,
                similarity_score=_decimal_or_none(item.similarity_score),
                similarity_category=item.similarity_category,
                confidence=_decimal(item.confidence),
                analysis_status=item.analysis_status,
                source_character_count=item.source_character_count,
                target_character_count=item.target_character_count,
                length_ratio=_decimal_or_none(item.length_ratio),
                number_consistency_status=item.number_consistency.status,
                date_consistency_status=item.date_consistency.status,
                measurement_consistency_status=(
                    item.measurement_consistency.status
                ),
                reference_consistency_status=(
                    item.reference_consistency.status
                ),
                negation_consistency_status=(
                    item.negation_consistency.status
                ),
                number_details_json={
                    **item.number_consistency.details,
                    "sourceValues": item.number_consistency.source_values,
                    "targetValues": item.number_consistency.target_values,
                },
                date_details_json={
                    **item.date_consistency.details,
                    "sourceValues": item.date_consistency.source_values,
                    "targetValues": item.date_consistency.target_values,
                },
                measurement_details_json={
                    **item.measurement_consistency.details,
                    "sourceValues": (
                        item.measurement_consistency.source_values
                    ),
                    "targetValues": (
                        item.measurement_consistency.target_values
                    ),
                },
                reference_details_json={
                    **item.reference_consistency.details,
                    "sourceValues": item.reference_consistency.source_values,
                    "targetValues": item.reference_consistency.target_values,
                },
                negation_details_json={
                    **item.negation_consistency.details,
                    "sourceValues": item.negation_consistency.source_values,
                    "targetValues": item.negation_consistency.target_values,
                },
                chunk_count_source=item.chunk_count_source,
                chunk_count_target=item.chunk_count_target,
                metrics_json=dict(item.metrics),
                warnings_json=list(item.warnings),
            )
            for item in pipeline.results
        ]
        await self.results.add_many(models, batch_size=self.batch_size)
        section_models = [
            SectionSimilaritySummary(
                similarity_run_id=run.id,
                detected_section_id=item.detected_section_id,
                canonical_section_code=item.canonical_section_code[:100],
                total_groups=item.total_groups,
                eligible_groups=item.eligible_groups,
                analysed_groups=item.analysed_groups,
                average_similarity=_decimal_or_none(
                    item.average_similarity
                ),
                minimum_similarity=_decimal_or_none(
                    item.minimum_similarity
                ),
                low_similarity_groups=item.low_similarity_groups,
                number_mismatches=item.number_mismatches,
                date_mismatches=item.date_mismatches,
                measurement_mismatches=item.measurement_mismatches,
                reference_mismatches=item.reference_mismatches,
                negation_mismatches=item.negation_mismatches,
                pairwise_summary_json=dict(item.pairwise_summary),
                metrics_json=dict(item.metrics),
            )
            for item in pipeline.section_summaries
        ]
        await self.sections.add_many(
            section_models, batch_size=self.batch_size
        )
        finding_count, unavailable_codes = await self._persist_findings(
            job, run, pipeline
        )
        if unavailable_codes:
            warnings.append("SIMILARITY_FINDING_ENUMS_NOT_INTEGRATED")
            run.warnings_json = warnings
        pointer_linked = await self.runs.set_latest_for_file(
            document_file_id=job.document_file_id,
            similarity_run_id=run.id,
        )
        run.metrics_json = {
            **run.metrics_json,
            "findingCount": finding_count,
            "latestPointerLinked": pointer_linked,
        }
        job.status = (
            SimilarityJobStatus.PARTIALLY_COMPLETED
            if run.status is SimilarityRunStatus.PARTIALLY_COMPLETED
            else SimilarityJobStatus.COMPLETED
        )
        job.progress = 100
        job.current_stage = "Completed"
        job.completed_at = completed
        job.error_code = None
        job.error_message = None
        job.error_details_json = None
        job.result_summary_json = {
            "runId": str(run.id),
            "status": run.status.value,
            "averageSimilarity": (
                float(run.average_similarity)
                if run.average_similarity is not None
                else None
            ),
            "analysedGroups": run.analysed_group_count,
            "lowSimilarityGroups": run.low_similarity_groups,
            "findingCount": finding_count,
        }
        await self.session.flush()
        return run

    async def _persist_findings(
        self,
        job: SimilarityJob,
        run: SimilarityRun,
        pipeline: SimilarityPipelineResult,
    ) -> tuple[int, list[str]]:
        available_codes = {value.value for value in FindingCode}
        unavailable = sorted(
            {
                draft.finding_code
                for draft in pipeline.findings
                if draft.finding_code not in available_codes
            }
        )
        persisted = 0
        validation_rule_id = job.compliance_run.validation_rule_id
        finding_type = getattr(
            FindingType, "TRANSLATION_SIMILARITY", FindingType.STRUCTURE
        )
        for draft in pipeline.findings:
            if draft.finding_code not in available_codes:
                continue
            previous = await self.findings.find_previous_match(
                document_revision_id=job.document_revision_id,
                finding_code=draft.finding_code,
                source_reference=draft.source_reference,
                language_code=draft.language_code,
                detected_section_id=draft.detected_section_id,
            )
            source_hash = draft.metrics.get("sourceTextHash")
            target_hash = draft.metrics.get("targetTextHash")
            if (
                previous is not None
                and previous.metrics_json.get("sourceTextHash")
                == source_hash
                and previous.metrics_json.get("targetTextHash")
                == target_hash
            ):
                continue
            finding = ValidationFinding(
                compliance_run_id=job.compliance_run_id,
                similarity_run_id=run.id,
                document_id=job.document_id,
                document_revision_id=job.document_revision_id,
                document_file_id=job.document_file_id,
                validation_rule_id=validation_rule_id,
                finding_code=FindingCode(draft.finding_code),
                finding_type=finding_type,
                severity=FindingSeverity(draft.severity),
                status=FindingStatus.OPEN,
                title=draft.title[:500],
                description=draft.description[:4000],
                recommendation=draft.recommendation[:2000],
                container_id=draft.container_id,
                detected_section_id=draft.detected_section_id,
                translation_group_id=draft.translation_group_id,
                source_reference=(
                    draft.source_reference[:1000]
                    if draft.source_reference
                    else None
                ),
                language_code=draft.language_code,
                expected_value_json=draft.expected_value,
                actual_value_json=draft.actual_value,
                metrics_json={
                    **draft.metrics,
                    "similarityRunId": str(run.id),
                },
                is_system_generated=True,
                created_by=job.requested_by,
            )
            await self.findings.add(finding)
            await self.findings.add_occurrences(
                [
                    FindingOccurrence(
                        finding_id=finding.id,
                        compliance_run_id=job.compliance_run_id,
                        source_reference=draft.source_reference,
                        location_json={
                            "similarityRunId": str(run.id),
                            "translationGroupId": (
                                str(draft.translation_group_id)
                                if draft.translation_group_id
                                else None
                            ),
                        },
                        metrics_json=dict(draft.metrics),
                    )
                ]
            )
            persisted += 1
        return persisted, unavailable


def _decimal(value: float) -> Decimal:
    return Decimal(str(round(float(value), 6)))


def _decimal_or_none(value: float | None) -> Decimal | None:
    return _decimal(value) if value is not None else None
