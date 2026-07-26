"""Pure in-memory contracts for local glossary matching and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GlossaryValidationScope:
    """Business scope used for profile and exception resolution."""

    department_id: UUID | None = None
    document_type_id: UUID | None = None
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    document_file_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GlossaryTextBlock:
    """A bounded extracted/OCR text block; never a binary document."""

    text: str
    language_code: str
    source_type: str
    source_reference: str
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    section_definition_id: UUID | None = None
    translation_group_id: UUID | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class GlossaryMatchCandidate:
    glossary_term_id: UUID
    glossary_translation_id: UUID | None
    glossary_variant_id: UUID | None
    term_code: str
    concept_name: str
    term_type: str
    severity: str
    language_code: str
    source_type: str
    source_reference: str
    matched_text: str
    normalised_matched_text: str
    start_offset: int
    end_offset: int
    match_type: str
    is_preferred: bool
    is_forbidden: bool
    is_allowed_variant: bool
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    section_definition_id: UUID | None = None
    translation_group_id: UUID | None = None
    exception_id: UUID | None = None
    confidence: float = 1.0
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def context_key(self) -> str:
        """Prefer Phase 8 translation groups over broader fallbacks."""

        for prefix, value in (
            ("group", self.translation_group_id),
            ("container", self.container_id),
            ("block", self.extracted_block_id or self.ocr_block_id),
        ):
            if value is not None:
                return f"{prefix}:{value}"
        return f"reference:{self.source_reference}"


@dataclass(frozen=True, slots=True)
class GlossaryFindingSignal:
    """A Phase 8-compatible finding draft produced by glossary rules."""

    finding_code: str
    severity: str
    title: str
    description: str
    recommendation: str
    glossary_term_id: UUID
    language_code: str | None = None
    source_reference: str | None = None
    extracted_block_id: UUID | None = None
    ocr_block_id: UUID | None = None
    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    translation_group_id: UUID | None = None
    exception_id: UUID | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    document_revision_id: UUID | None = None
    is_system_generated: bool = True
    is_repeat: bool = False
    previous_finding_id: UUID | None = None
    deduplication_key: str | None = None


@dataclass(frozen=True, slots=True)
class GlossaryValidationResult:
    matches: tuple[GlossaryMatchCandidate, ...]
    findings: tuple[GlossaryFindingSignal, ...]
    total_terms: int
    matched_terms: int
    preferred_term_matches: int
    forbidden_term_matches: int
    missing_required_translations: int
    inconsistent_terms: int
    exception_applied_count: int
    metrics: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
