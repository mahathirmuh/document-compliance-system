"""Pairwise Phase 9 translation-similarity evidence."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.detected_section import DetectedSection
    from app.models.extracted_container import ExtractedContainer
    from app.models.similarity_run import SimilarityRun
    from app.models.translation_group import TranslationGroup
    from app.models.translation_group_member import TranslationGroupMember


class TranslationSimilarityResult(Base):
    """One pairwise comparison; raw document text is never retained here."""

    __tablename__ = "translation_similarity_results"
    __table_args__ = (
        UniqueConstraint(
            "similarity_run_id",
            "translation_group_id",
            "source_language_code",
            "target_language_code",
            name="uq_translation_similarity_result_pair",
        ),
        CheckConstraint(
            "(similarity_score IS NULL OR "
            "(similarity_score >= 0 AND similarity_score <= 1)) AND "
            "confidence >= 0 AND confidence <= 1",
            name="translation_similarity_results_score_range",
        ),
        CheckConstraint(
            "source_character_count >= 0 AND target_character_count >= 0 "
            "AND chunk_count_source >= 0 AND chunk_count_target >= 0",
            name="translation_similarity_results_counts",
        ),
        CheckConstraint(
            "length(source_text_hash) = 64 AND "
            "length(target_text_hash) = 64",
            name="translation_similarity_results_hash_length",
        ),
        Index(
            "ix_translation_similarity_results_run",
            "similarity_run_id",
        ),
        Index(
            "ix_translation_similarity_results_group",
            "translation_group_id",
        ),
        Index(
            "ix_translation_similarity_results_section",
            "detected_section_id",
        ),
        Index(
            "ix_translation_similarity_results_languages",
            "source_language_code",
            "target_language_code",
        ),
        Index(
            "ix_translation_similarity_results_category",
            "similarity_category",
        ),
        Index(
            "ix_translation_similarity_results_score",
            "similarity_score",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    similarity_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    translation_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    detected_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_reference: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    source_language_code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    target_language_code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    source_member_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_group_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_member_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_group_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    similarity_score: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    similarity_category: Mapped[SimilarityCategory] = mapped_column(
        Enum(
            SimilarityCategory,
            name="similarity_category",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(7, 6), nullable=False
    )
    analysis_status: Mapped[SimilarityAnalysisStatus] = mapped_column(
        Enum(
            SimilarityAnalysisStatus,
            name="similarity_analysis_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_character_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    target_character_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    length_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    number_consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(
            ConsistencyStatus,
            name="similarity_consistency_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    date_consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(
            ConsistencyStatus,
            name="similarity_consistency_status",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    measurement_consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(
            ConsistencyStatus,
            name="similarity_consistency_status",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    reference_consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(
            ConsistencyStatus,
            name="similarity_consistency_status",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    negation_consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(
            ConsistencyStatus,
            name="similarity_consistency_status",
            values_callable=enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    number_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    date_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    measurement_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    reference_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    negation_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    chunk_count_source: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    chunk_count_target: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    warnings_json: Mapped[list[str] | list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    similarity_run: Mapped[SimilarityRun] = relationship(
        back_populates="results",
        foreign_keys=[similarity_run_id],
    )
    translation_group: Mapped[TranslationGroup] = relationship(
        foreign_keys=[translation_group_id]
    )
    detected_section: Mapped[DetectedSection | None] = relationship(
        foreign_keys=[detected_section_id]
    )
    container: Mapped[ExtractedContainer | None] = relationship(
        foreign_keys=[container_id]
    )
    source_member: Mapped[TranslationGroupMember | None] = relationship(
        foreign_keys=[source_member_id]
    )
    target_member: Mapped[TranslationGroupMember | None] = relationship(
        foreign_keys=[target_member_id]
    )

    @validates(
        "source_language_code",
        "target_language_code",
    )
    def normalize_language(self, _: str, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"id", "en", "zh"}:
            raise ValueError("Similarity language must be id, en, or zh.")
        return normalized

    @validates("source_text_hash", "target_text_hash")
    def normalize_text_hash(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError("Text hashes must be 64 lowercase hex digits.")
        return normalized
