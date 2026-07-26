"""Canonical sections detected within one compliance run."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.compliance_enums import (
    SectionAliasMatchType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.extracted_container import ExtractedContainer
    from app.models.section_definition import SectionDefinition
    from app.models.section_language_result import SectionLanguageResult
    from app.models.translation_group import TranslationGroup
    from app.models.validation_finding import ValidationFinding


class DetectedSection(Base):
    """One bounded occurrence of a canonical section."""

    __tablename__ = "detected_sections"
    __table_args__ = (
        UniqueConstraint(
            "compliance_run_id",
            "section_order",
            name="uq_detected_sections_run_order",
        ),
        CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="detected_sections_confidence_range",
        ),
        CheckConstraint(
            "section_order >= 0",
            name="detected_sections_order_nonnegative",
        ),
        Index("ix_detected_sections_compliance_run_id", "compliance_run_id"),
        Index(
            "ix_detected_sections_section_definition_id",
            "section_definition_id",
        ),
        Index("ix_detected_sections_canonical_code", "canonical_code"),
        Index("ix_detected_sections_container_id", "container_id"),
        Index("ix_detected_sections_heading_block_id", "heading_block_id"),
        Index("ix_detected_sections_is_required", "is_required"),
        Index("ix_detected_sections_is_complete", "is_complete"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    compliance_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("section_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    canonical_code: Mapped[str] = mapped_column(String(64), nullable=False)
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    end_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    heading_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    heading_text: Mapped[str] = mapped_column(Text, nullable=False)
    heading_language_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    match_type: Mapped[SectionAliasMatchType] = mapped_column(
        Enum(
            SectionAliasMatchType,
            name="section_alias_match_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    match_confidence: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
    )
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    language_presence_json: Mapped[dict[str, Any]] = mapped_column(
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
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    compliance_run: Mapped[ComplianceRun] = relationship(
        back_populates="detected_sections",
        foreign_keys=[compliance_run_id],
    )
    section_definition: Mapped[SectionDefinition | None] = relationship(
        back_populates="detected_sections",
        foreign_keys=[section_definition_id],
    )
    container: Mapped[ExtractedContainer | None] = relationship(
        foreign_keys=[container_id]
    )
    language_results: Mapped[list[SectionLanguageResult]] = relationship(
        back_populates="detected_section",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SectionLanguageResult.language_code",
    )
    translation_groups: Mapped[list[TranslationGroup]] = relationship(
        back_populates="detected_section",
        passive_deletes=True,
    )
    findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="detected_section",
        passive_deletes=True,
    )
