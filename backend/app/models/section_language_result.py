"""Per-language evidence within a detected canonical section."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.compliance_enums import (
    SectionLanguagePresenceStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.detected_section import DetectedSection


class SectionLanguageResult(Base):
    """Presence, coverage, and confidence for one section language."""

    __tablename__ = "section_language_results"
    __table_args__ = (
        UniqueConstraint(
            "detected_section_id",
            "language_code",
            name="uq_section_language_results_section_language",
        ),
        CheckConstraint(
            "block_count >= 0 AND character_count >= 0",
            name="section_language_results_counts_nonnegative",
        ),
        CheckConstraint(
            "coverage_percentage >= 0 AND coverage_percentage <= 100",
            name="section_language_results_coverage_range",
        ),
        CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="section_language_results_confidence_range",
        ),
        Index(
            "ix_section_language_results_detected_section_id",
            "detected_section_id",
        ),
        Index("ix_section_language_results_language_code", "language_code"),
        Index("ix_section_language_results_presence_status", "presence_status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    detected_section_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    presence_status: Mapped[SectionLanguagePresenceStatus] = mapped_column(
        Enum(
            SectionLanguagePresenceStatus,
            name="section_language_presence_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    block_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    character_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    coverage_percentage: Mapped[Decimal] = mapped_column(
        Numeric(7, 3),
        nullable=False,
        default=0,
        server_default="0",
    )
    average_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )
    first_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    last_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    detected_section: Mapped[DetectedSection] = relationship(
        back_populates="language_results",
        foreign_keys=[detected_section_id],
    )
