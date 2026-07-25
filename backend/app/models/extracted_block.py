"""Unified searchable content blocks produced by Phase 6 extractors."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.extracted_container import ExtractedContainer
    from app.models.extraction_run import ExtractionRun


class ExtractedBlockType(StrEnum):
    """Cross-format block classifications."""

    TEXT = "TEXT"
    PARAGRAPH = "PARAGRAPH"
    HEADING = "HEADING"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    TABLE_CELL = "TABLE_CELL"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    WORKSHEET_TITLE = "WORKSHEET_TITLE"
    CELL = "CELL"
    MERGED_CELL = "MERGED_CELL"
    FORMULA = "FORMULA"
    PAGE_NUMBER = "PAGE_NUMBER"
    UNKNOWN = "UNKNOWN"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ExtractedBlock(Base):
    """Smallest ordered and searchable normalized extraction unit."""

    __tablename__ = "extracted_blocks"
    _postgresql_search_index = Index(
        "ix_extracted_blocks_normalised_text_search",
        sql_text(
            "to_tsvector("
            "'simple'::regconfig, "
            "(normalised_text || ' '::text) || source_reference::text"
            ")"
        ),
        postgresql_using="gin",
    ).ddl_if(dialect="postgresql")

    __table_args__ = (
        CheckConstraint(
            "block_order >= 0",
            name="block_order_nonnegative",
        ),
        CheckConstraint(
            "heading_level IS NULL OR "
            "(heading_level >= 1 AND heading_level <= 9)",
            name="heading_level_range",
        ),
        CheckConstraint(
            "character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        CheckConstraint(
            "parent_block_id IS NULL OR parent_block_id <> id",
            name="not_self_parent",
        ),
        Index(
            "ix_extracted_blocks_extraction_run_id",
            "extraction_run_id",
        ),
        Index("ix_extracted_blocks_container_id", "container_id"),
        Index("ix_extracted_blocks_block_type", "block_type"),
        Index("ix_extracted_blocks_block_order", "block_order"),
        Index("ix_extracted_blocks_parent_block_id", "parent_block_id"),
        Index(
            "ix_extracted_blocks_source_reference",
            "source_reference",
        ),
        Index(
            "ix_extracted_blocks_run_order",
            "extraction_run_id",
            "container_id",
            "block_order",
        ),
        _postgresql_search_index,
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    container_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    block_type: Mapped[ExtractedBlockType] = mapped_column(
        Enum(
            ExtractedBlockType,
            name="extracted_block_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    block_order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    normalised_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    style_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    heading_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    location_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    character_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    word_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    extraction_run: Mapped[ExtractionRun] = relationship(
        back_populates="blocks",
        foreign_keys=[extraction_run_id],
    )
    container: Mapped[ExtractedContainer] = relationship(
        back_populates="blocks",
        foreign_keys=[container_id],
    )
    parent_block: Mapped[ExtractedBlock | None] = relationship(
        back_populates="child_blocks",
        remote_side=[id],
        foreign_keys=[parent_block_id],
    )
    child_blocks: Mapped[list[ExtractedBlock]] = relationship(
        back_populates="parent_block",
        foreign_keys=[parent_block_id],
    )
