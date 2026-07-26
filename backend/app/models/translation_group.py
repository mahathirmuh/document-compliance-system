"""Structurally inferred multilingual content groups."""

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
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.compliance_enums import TranslationGroupType, enum_values

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.detected_section import DetectedSection
    from app.models.extracted_container import ExtractedContainer
    from app.models.translation_group_member import TranslationGroupMember
    from app.models.validation_finding import ValidationFinding


class TranslationGroup(Base):
    """A positional/structural language group, never a semantic assertion."""

    __tablename__ = "translation_groups"
    __table_args__ = (
        UniqueConstraint(
            "compliance_run_id",
            "group_index",
            name="uq_translation_groups_run_index",
        ),
        CheckConstraint(
            "group_index >= 0 AND start_block_order >= 0 "
            "AND end_block_order >= start_block_order",
            name="translation_groups_order_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="translation_groups_confidence_range",
        ),
        Index("ix_translation_groups_compliance_run_id", "compliance_run_id"),
        Index("ix_translation_groups_container_id", "container_id"),
        Index(
            "ix_translation_groups_detected_section_id",
            "detected_section_id",
        ),
        Index("ix_translation_groups_group_type", "group_type"),
        Index("ix_translation_groups_is_complete", "is_complete"),
        Index("ix_translation_groups_is_order_valid", "is_order_valid"),
        Index("ix_translation_groups_confidence", "confidence"),
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
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    group_type: Mapped[TranslationGroupType] = mapped_column(
        Enum(
            TranslationGroupType,
            name="translation_group_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    start_block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    end_block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    expected_languages_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    detected_languages_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    language_order_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_order_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
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
        back_populates="translation_groups",
        foreign_keys=[compliance_run_id],
    )
    container: Mapped[ExtractedContainer | None] = relationship(
        foreign_keys=[container_id]
    )
    detected_section: Mapped[DetectedSection | None] = relationship(
        back_populates="translation_groups",
        foreign_keys=[detected_section_id],
    )
    members: Mapped[list[TranslationGroupMember]] = relationship(
        back_populates="translation_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationGroupMember.block_order",
    )
    findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="translation_group",
        passive_deletes=True,
    )
