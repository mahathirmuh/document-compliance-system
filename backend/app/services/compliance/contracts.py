"""Pure in-memory result contracts for section/group/score orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class HeadingCandidate:
    block: object
    block_id: object | None
    container_id: object | None
    container_type: str
    container_index: int
    block_order: int
    source_reference: str
    text: str
    normalised_text: str
    heading_level: int | None
    candidate_score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionMatch:
    candidate: HeadingCandidate
    canonical_code: str
    language_code: str
    match_type: str
    confidence: float
    alias_text: str
    alias_priority: int = 0
    display_order: int = 0
    is_repeatable: bool = False
    profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class DetectedSection:
    canonical_code: str
    container_id: str | None
    container_type: str
    heading_block_id: str | None
    heading_text: str
    heading_language_code: str | None
    match_type: str
    match_confidence: float
    section_order: int
    start_block_order: int
    end_block_order: int
    start_block_id: str | None = None
    end_block_id: str | None = None
    source_reference: str | None = None
    is_required: bool = False
    is_complete: bool = True
    language_presence: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranslationGroupMember:
    block_id: str | None
    language_code: str
    block_order: int
    text_snapshot: str
    confidence: float
    source_reference: str
    source_type: str | None = None
    position: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranslationGroup:
    container_id: str | None
    group_index: int
    group_type: str
    source_reference: str
    expected_languages: tuple[str, ...]
    detected_languages: tuple[str, ...]
    language_order: tuple[str, ...]
    members: tuple[TranslationGroupMember, ...]
    is_complete: bool
    is_order_valid: bool
    confidence: float
    detected_section_code: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FindingDraft:
    finding_code: str
    finding_type: str
    severity: str
    title: str
    description: str
    recommendation: str
    status: str = "OPEN"
    id: str | None = None
    compliance_run_id: str | None = None
    document_id: str | None = None
    document_revision_id: str | None = None
    document_file_id: str | None = None
    validation_rule_id: str | None = None
    container_id: str | None = None
    detected_section_id: str | None = None
    section_code: str | None = None
    translation_group_id: str | None = None
    translation_group_signature: str | None = None
    extracted_block_id: str | None = None
    ocr_block_id: str | None = None
    page_number: int | None = None
    worksheet_name: str | None = None
    cell_coordinate: str | None = None
    source_reference: str | None = None
    location: dict[str, object] = field(default_factory=dict)
    language_code: str | None = None
    expected_value: dict[str, object] = field(default_factory=dict)
    actual_value: dict[str, object] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)
    is_system_generated: bool = True
    is_repeat: bool = False
    previous_finding_id: str | None = None
    assigned_to: str | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None
    resolved_by: str | None = None
    resolution_comment: str | None = None
    false_positive_by: str | None = None
    false_positive_reason: str | None = None
    reopen_reason: str | None = None
    accepted_risk_reason: str | None = None
    accepted_risk_expiry: str | None = None
    deduplication_key: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatorResult:
    validator_code: str
    status: str
    score: float
    maximum_score: float
    findings: tuple[object, ...] = ()
    metrics: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TableLayout:
    layout: str
    language_columns: dict[str, int] = field(default_factory=dict)
    language_rows: dict[str, int] = field(default_factory=dict)
    confidence: float = 0.0
    header_order: tuple[str, ...] = ()
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    weighted_score: float
    major_penalty: float
    minor_penalty: float
    total_penalty: float
    score_before_cap: float
    score_cap: float | None
    final_score: float
    maximum_score: float
    validators: dict[str, dict[str, object]]
    finding_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class StatusDecision:
    status: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    score_change: float
    previous_status: str
    current_status: str
    languages_added: tuple[str, ...]
    languages_removed: tuple[str, ...]
    sections_added: tuple[str, ...]
    sections_removed: tuple[str, ...]
    new_findings: tuple[object, ...]
    not_reproduced_findings: tuple[object, ...]
    repeated_findings: tuple[object, ...]
    translation_group_complete_change: int
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompliancePipelineResult:
    context: object
    validator_results: tuple[object, ...]
    findings: tuple[object, ...]
    score: ScoreBreakdown
    status: StatusDecision
    warnings: tuple[str, ...] = ()


def next_group_index(groups: Sequence[TranslationGroup]) -> int:
    if not groups:
        return 0
    return max(group.group_index for group in groups) + 1
