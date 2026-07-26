"""Persistence-independent data exchanged by similarity services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    SimilarityRunStatus,
)
from app.schemas.base import ApiSchema


class SimilarityThresholds(ApiSchema):
    high: float = Field(default=0.85, ge=0, le=1)
    acceptable: float = Field(default=0.72, ge=0, le=1)
    review: float = Field(default=0.58, ge=0, le=1)
    critical_low: float = Field(default=0.35, ge=0, le=1)


class SimilarityOptions(ApiSchema):
    primary_language: str | None = None
    required_pairs: list[tuple[str, str]] = Field(default_factory=list)
    optional_pairs: list[tuple[str, str]] = Field(default_factory=list)
    thresholds: SimilarityThresholds = Field(
        default_factory=SimilarityThresholds
    )
    length_ratio_ranges: dict[str, dict[str, float]] = Field(
        default_factory=dict
    )
    minimum_characters: int = Field(default=10, ge=1)
    minimum_group_confidence: float = Field(default=0.65, ge=0, le=1)
    skip_code_like_text: bool = True
    skip_numeric_only_text: bool = True


class SimilarityMemberData(ApiSchema):
    id: UUID | None = None
    language_code: str
    text: str
    confidence: float = Field(default=0, ge=0, le=1)
    block_order: int = Field(default=0, ge=0)
    source_reference: str = ""
    source_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimilarityGroupData(ApiSchema):
    id: UUID
    detected_section_id: UUID | None = None
    canonical_section_code: str | None = None
    container_id: UUID | None = None
    source_reference: str
    group_index: int = Field(ge=0)
    group_type: str
    confidence: float = Field(ge=0, le=1)
    members: list[SimilarityMemberData] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class SimilarityContext(ApiSchema):
    document_id: UUID
    document_revision_id: UUID
    document_file_id: UUID
    compliance_run_id: UUID
    language_detection_run_id: UUID
    source_content_hash: str
    groups: list[SimilarityGroupData] = Field(default_factory=list)
    options: SimilarityOptions = Field(default_factory=SimilarityOptions)
    warnings: list[str] = Field(default_factory=list)
    source_quality: dict[str, float | bool | None] = Field(
        default_factory=dict
    )
    quality_configuration: dict[str, Any] = Field(default_factory=dict)


class TextEligibilityResult(ApiSchema):
    eligible: bool
    status: SimilarityAnalysisStatus
    reason: str | None = None
    normalized_text: str
    character_count: int = Field(ge=0)


class TextChunk(ApiSchema):
    index: int = Field(ge=0)
    text: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=0)


class ChunkingResult(ApiSchema):
    chunks: list[TextChunk] = Field(default_factory=list)
    original_character_count: int = Field(ge=0)
    processed_character_count: int = Field(ge=0)
    complete: bool
    warnings: list[str] = Field(default_factory=list)


class ConsistencyCheckResult(ApiSchema):
    status: ConsistencyStatus
    source_values: list[str] = Field(default_factory=list)
    target_values: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SimilarityResultDraft(ApiSchema):
    translation_group_id: UUID
    detected_section_id: UUID | None = None
    canonical_section_code: str | None = None
    container_id: UUID | None = None
    source_reference: str
    source_language_code: str
    target_language_code: str
    source_member_id: UUID | None = None
    target_member_id: UUID | None = None
    source_text_hash: str
    target_text_hash: str
    similarity_score: float | None = Field(default=None, ge=0, le=1)
    similarity_category: SimilarityCategory
    confidence: float = Field(ge=0, le=1)
    analysis_status: SimilarityAnalysisStatus
    source_character_count: int = Field(ge=0)
    target_character_count: int = Field(ge=0)
    length_ratio: float | None = Field(default=None, ge=0)
    number_consistency: ConsistencyCheckResult
    date_consistency: ConsistencyCheckResult
    measurement_consistency: ConsistencyCheckResult
    reference_consistency: ConsistencyCheckResult
    negation_consistency: ConsistencyCheckResult
    chunk_count_source: int = Field(default=0, ge=0)
    chunk_count_target: int = Field(default=0, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SectionSimilarityDraft(ApiSchema):
    detected_section_id: UUID | None = None
    canonical_section_code: str
    total_groups: int = Field(ge=0)
    eligible_groups: int = Field(ge=0)
    analysed_groups: int = Field(ge=0)
    average_similarity: float | None = Field(default=None, ge=0, le=1)
    minimum_similarity: float | None = Field(default=None, ge=0, le=1)
    low_similarity_groups: int = Field(ge=0)
    number_mismatches: int = Field(ge=0)
    date_mismatches: int = Field(ge=0)
    measurement_mismatches: int = Field(ge=0)
    reference_mismatches: int = Field(ge=0)
    negation_mismatches: int = Field(ge=0)
    pairwise_summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class SimilarityFindingDraft(ApiSchema):
    finding_code: str
    severity: str
    title: str
    description: str
    recommendation: str
    translation_group_id: UUID | None = None
    detected_section_id: UUID | None = None
    container_id: UUID | None = None
    source_reference: str | None = None
    language_code: str | None = None
    expected_value: dict[str, Any] = Field(default_factory=dict)
    actual_value: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class SimilarityAggregate(ApiSchema):
    status: SimilarityRunStatus
    translation_group_count: int = Field(ge=0)
    eligible_group_count: int = Field(ge=0)
    analysed_group_count: int = Field(ge=0)
    skipped_group_count: int = Field(ge=0)
    failed_group_count: int = Field(ge=0)
    average_similarity: float | None = Field(default=None, ge=0, le=1)
    minimum_similarity: float | None = Field(default=None, ge=0, le=1)
    maximum_similarity: float | None = Field(default=None, ge=0, le=1)
    pair_averages: dict[str, float | None] = Field(default_factory=dict)
    high_similarity_groups: int = Field(ge=0)
    review_similarity_groups: int = Field(ge=0)
    low_similarity_groups: int = Field(ge=0)
    unavailable_similarity_groups: int = Field(ge=0)
    mismatch_counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class SimilarityPipelineResult(ApiSchema):
    context: SimilarityContext
    results: list[SimilarityResultDraft] = Field(default_factory=list)
    section_summaries: list[SectionSimilarityDraft] = Field(
        default_factory=list
    )
    findings: list[SimilarityFindingDraft] = Field(default_factory=list)
    aggregate: SimilarityAggregate
    provider_info: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
