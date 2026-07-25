"""Atomic, batch-oriented persistence for language detection results."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.language_block_result import LanguageBlockResult
from app.models.language_container_summary import LanguageContainerSummary
from app.models.language_detection_job import (
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
)
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.repositories.language_container_summary_repository import (
    LanguageContainerSummaryRepository,
)
from app.repositories.language_detection_job_repository import (
    LanguageDetectionJobRepository,
)
from app.repositories.language_detection_run_repository import (
    LanguageDetectionRunRepository,
)
from app.schemas.language_internal import LanguagePipelineResultData
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)

ItemT = TypeVar("ItemT")


def _chunks(
    items: Sequence[ItemT],
    size: int,
) -> Iterator[Sequence[ItemT]]:
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


class LanguagePersistenceService:
    """Persist a new immutable run without overwriting prior history."""

    def __init__(
        self,
        session: AsyncSession,
        config: LanguageRuntimeConfig,
    ) -> None:
        self.session = session
        self.config = config
        self.jobs = LanguageDetectionJobRepository(session)
        self.runs = LanguageDetectionRunRepository(session)
        self.blocks = LanguageBlockResultRepository(session)
        self.containers = LanguageContainerSummaryRepository(session)

    async def persist_result(
        self,
        *,
        job: LanguageDetectionJob,
        result: LanguagePipelineResultData,
        started_at: datetime,
        completed_at: datetime,
    ) -> LanguageDetectionRun:
        if len(result.blocks) > self.config.maximum_blocks:
            raise ValueError(
                "Language result exceeds the configured block limit."
            )
        aggregate = result.aggregate
        async with self.session.begin_nested():
            run = await self.runs.create(
                LanguageDetectionRun(
                    document_id=job.document_id,
                    document_revision_id=job.document_revision_id,
                    document_file_id=job.document_file_id,
                    extraction_run_id=job.extraction_run_id,
                    ocr_run_id=job.ocr_run_id,
                    job_id=job.id,
                    detector_name=result.detector_name,
                    detector_version=result.detector_version,
                    status=LanguageDetectionRunStatus.COMPLETED,
                    source_content_hash=result.source_content_hash,
                    total_blocks=aggregate.total_blocks,
                    eligible_blocks=aggregate.eligible_blocks,
                    detected_blocks=aggregate.detected_blocks,
                    unknown_blocks=aggregate.unknown_blocks,
                    mixed_blocks=aggregate.mixed_blocks,
                    indonesian_blocks=aggregate.indonesian_blocks,
                    english_blocks=aggregate.english_blocks,
                    chinese_blocks=aggregate.chinese_blocks,
                    other_blocks=aggregate.other_blocks,
                    total_characters=aggregate.total_characters,
                    indonesian_characters=(
                        aggregate.indonesian_characters
                    ),
                    english_characters=aggregate.english_characters,
                    chinese_characters=aggregate.chinese_characters,
                    mixed_characters=aggregate.mixed_characters,
                    unknown_characters=aggregate.unknown_characters,
                    average_confidence=aggregate.average_confidence,
                    warnings_json=list(result.warnings),
                    metadata_json={
                        "preliminary": True,
                        "preliminaryLabel": "Preliminary Coverage",
                        "coverage": aggregate.coverage.model_dump(
                            mode="json",
                            by_alias=True,
                        ),
                        "dominantLanguage": (
                            aggregate.dominant_language.value
                        ),
                        "otherCharacters": aggregate.other_characters,
                    },
                    requested_by=job.requested_by,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            )
            await self._persist_blocks(run, result)
            await self._persist_containers(run, result)
            await self.runs.set_latest_by_ids(
                document_file_id=job.document_file_id,
                language_detection_run_id=run.id,
            )
            job.source_content_hash = result.source_content_hash
            await self.jobs.mark_completed(
                job,
                status=LanguageDetectionJobStatus.COMPLETED,
                completed_at=completed_at,
                result_summary={
                    "runId": str(run.id),
                    "status": LanguageDetectionJobStatus.COMPLETED.value,
                    "totalBlocks": aggregate.total_blocks,
                    "eligibleBlocks": aggregate.eligible_blocks,
                    "detectedBlocks": aggregate.detected_blocks,
                    "unknownBlocks": aggregate.unknown_blocks,
                    "mixedBlocks": aggregate.mixed_blocks,
                    "languagePresence": (
                        aggregate.coverage.language_presence.model_dump(
                            mode="json",
                            by_alias=True,
                        )
                    ),
                    "preliminary": True,
                },
            )
        return run

    async def _persist_blocks(
        self,
        run: LanguageDetectionRun,
        result: LanguagePipelineResultData,
    ) -> None:
        models = [
            LanguageBlockResult(
                language_detection_run_id=run.id,
                extracted_block_id=block.source.extracted_block_id,
                ocr_block_id=block.source.ocr_block_id,
                container_id=block.source.container_id,
                source_type=block.source.source_type,
                source_reference=block.source.source_reference,
                language_code=block.detection.language_code,
                primary_language_code=(
                    block.detection.primary_language_code
                ),
                confidence=block.detection.confidence,
                is_mixed=block.detection.is_mixed,
                detected_languages_json=[
                    score.model_dump(mode="json", by_alias=True)
                    for score in block.detection.detected_languages
                ],
                script_statistics_json=(
                    block.detection.script_statistics.model_dump(
                        mode="json",
                        by_alias=True,
                    )
                ),
                eligibility_status=block.detection.eligibility.status,
                eligibility_reason=block.detection.eligibility.reason,
                character_count=block.detection.character_count,
                latin_character_count=(
                    block.detection.latin_character_count
                ),
                han_character_count=block.detection.han_character_count,
                word_count=block.detection.word_count,
                metadata_json={
                    **block.detection.metadata,
                    "source": block.source.source_metadata,
                    "sourceConfidence": block.source.source_confidence,
                    "containerIndex": block.source.container_index,
                    "blockOrder": block.source.block_order,
                    "pageNumber": block.source.page_number,
                },
            )
            for block in result.blocks
        ]
        for batch in _chunks(models, self.config.database_batch_size):
            await self.blocks.bulk_create(batch)
            for model in batch:
                self.session.expunge(model)

    async def _persist_containers(
        self,
        run: LanguageDetectionRun,
        result: LanguagePipelineResultData,
    ) -> None:
        models = []
        for container in result.containers:
            aggregate = container.aggregate
            models.append(
                LanguageContainerSummary(
                    language_detection_run_id=run.id,
                    container_id=container.container_id,
                    container_type=container.container_type,
                    container_name=container.container_name,
                    container_index=container.container_index,
                    total_blocks=aggregate.total_blocks,
                    eligible_blocks=aggregate.eligible_blocks,
                    indonesian_blocks=aggregate.indonesian_blocks,
                    english_blocks=aggregate.english_blocks,
                    chinese_blocks=aggregate.chinese_blocks,
                    mixed_blocks=aggregate.mixed_blocks,
                    unknown_blocks=aggregate.unknown_blocks,
                    other_blocks=aggregate.other_blocks,
                    indonesian_characters=(
                        aggregate.indonesian_characters
                    ),
                    english_characters=aggregate.english_characters,
                    chinese_characters=aggregate.chinese_characters,
                    mixed_characters=aggregate.mixed_characters,
                    unknown_characters=aggregate.unknown_characters,
                    dominant_language=aggregate.dominant_language.value,
                    language_presence_json=(
                        aggregate.coverage.language_presence.model_dump(
                            mode="json",
                            by_alias=True,
                        )
                    ),
                    coverage_json={
                        "blockCoverage": (
                            aggregate.coverage.block_coverage.model_dump(
                                mode="json",
                                by_alias=True,
                            )
                        ),
                        "characterCoverage": (
                            aggregate.coverage.character_coverage.model_dump(
                                mode="json",
                                by_alias=True,
                            )
                        ),
                        "preliminary": True,
                    },
                )
            )
        for batch in _chunks(models, self.config.database_batch_size):
            await self.containers.bulk_create(batch)
            for model in batch:
                self.session.expunge(model)
