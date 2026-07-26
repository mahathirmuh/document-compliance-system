"""Section-level aggregates for Phase 9 similarity analysis."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.detected_section import DetectedSection
    from app.models.similarity_run import SimilarityRun


class SectionSimilaritySummary(Base):
    """Bounded section aggregate without full source text."""

    __tablename__ = "section_similarity_summaries"
    __table_args__ = (
        UniqueConstraint(
            "similarity_run_id",
            "detected_section_id",
            "canonical_section_code",
            name="uq_section_similarity_summary_run_section",
        ),
        CheckConstraint(
            "total_groups >= 0 AND eligible_groups >= 0 "
            "AND analysed_groups >= 0 AND low_similarity_groups >= 0",
            name="section_similarity_summaries_group_counts",
        ),
        CheckConstraint(
            "(average_similarity IS NULL OR "
            "(average_similarity >= 0 AND average_similarity <= 1)) AND "
            "(minimum_similarity IS NULL OR "
            "(minimum_similarity >= 0 AND minimum_similarity <= 1))",
            name="section_similarity_summaries_score_range",
        ),
        Index(
            "ix_section_similarity_summaries_run",
            "similarity_run_id",
        ),
        Index(
            "ix_section_similarity_summaries_section",
            "detected_section_id",
        ),
        Index(
            "ix_section_similarity_summaries_code",
            "canonical_section_code",
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
    detected_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    canonical_section_code: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    total_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    eligible_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    analysed_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    average_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    minimum_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    low_similarity_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    number_mismatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    date_mismatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    measurement_mismatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    reference_mismatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    negation_mismatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pairwise_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    similarity_run: Mapped[SimilarityRun] = relationship(
        back_populates="section_summaries",
        foreign_keys=[similarity_run_id],
    )
    detected_section: Mapped[DetectedSection | None] = relationship(
        foreign_keys=[detected_section_id]
    )
