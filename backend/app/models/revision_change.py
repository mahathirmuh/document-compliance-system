"""Bounded entity-level changes for a retained revision comparison."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
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
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base
from app.models.revision_comparison_job import revision_enum_values

REVISION_TEXT_SNAPSHOT_MAX_CHARACTERS = 4000


class RevisionChangeType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    MOVED = "MOVED"
    UNCHANGED = "UNCHANGED"
    SPLIT = "SPLIT"
    MERGED = "MERGED"


class RevisionEntityType(StrEnum):
    SECTION = "SECTION"
    CONTAINER = "CONTAINER"
    TRANSLATION_GROUP = "TRANSLATION_GROUP"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    TABLE_CELL = "TABLE_CELL"
    XLSX_CELL = "XLSX_CELL"
    PDF_BLOCK = "PDF_BLOCK"
    HEADING = "HEADING"


class RevisionChange(Base):
    """One aligned entity outcome; text snapshots are intentionally bounded."""

    __tablename__ = "revision_changes"
    __table_args__ = (
        CheckConstraint(
            "(text_similarity IS NULL OR "
            "(text_similarity >= 0 AND text_similarity <= 1)) "
            "AND (structural_similarity IS NULL OR "
            "(structural_similarity >= 0 AND structural_similarity <= 1)) "
            "AND (alignment_confidence IS NULL OR "
            "(alignment_confidence >= 0 AND alignment_confidence <= 1))",
            name="revision_changes_similarity_ranges",
        ),
        CheckConstraint(
            "character_change_count >= 0 AND word_change_count >= 0",
            name="revision_changes_counts_nonnegative",
        ),
        Index(
            "ix_revision_changes_comparison_id",
            "revision_comparison_id",
        ),
        Index("ix_revision_changes_change_type", "change_type"),
        Index("ix_revision_changes_entity_type", "entity_type"),
        Index("ix_revision_changes_language_code", "language_code"),
        Index("ix_revision_changes_base_section_id", "base_section_id"),
        Index("ix_revision_changes_target_section_id", "target_section_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    revision_comparison_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("revision_comparisons.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_type: Mapped[RevisionChangeType] = mapped_column(
        Enum(
            RevisionChangeType,
            name="revision_change_type",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    entity_type: Mapped[RevisionEntityType] = mapped_column(
        Enum(
            RevisionEntityType,
            name="revision_entity_type",
            values_callable=revision_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    base_container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_translation_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_translation_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    language_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    source_reference_base: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    source_reference_target: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    base_text_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    target_text_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    text_similarity: Mapped[float | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    structural_similarity: Mapped[float | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    alignment_confidence: Mapped[float | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    character_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    word_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @validates("base_text_snapshot", "target_text_snapshot")
    def bound_snapshot(self, _: str, value: str | None) -> str | None:
        if value is None:
            return None
        return value[:REVISION_TEXT_SNAPSHOT_MAX_CHARACTERS]
