"""Structured cells for extracted tables."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.extracted_table import ExtractedTable


class ExtractedTableCell(Base):
    """One normalized table cell, including merged-cell span metadata."""

    __tablename__ = "extracted_table_cells"
    __table_args__ = (
        UniqueConstraint(
            "extracted_table_id",
            "row_index",
            "column_index",
            name="uq_extracted_table_cells_table_position",
        ),
        CheckConstraint(
            "row_index >= 0 AND column_index >= 0",
            name="position_nonnegative",
        ),
        CheckConstraint(
            "row_span >= 1 AND column_span >= 1",
            name="span_positive",
        ),
        Index(
            "ix_extracted_table_cells_extracted_table_id",
            "extracted_table_id",
        ),
        Index(
            "ix_extracted_table_cells_coordinate",
            "coordinate",
        ),
        Index(
            "ix_extracted_table_cells_table_position",
            "extracted_table_id",
            "row_index",
            "column_index",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    extracted_table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row_span: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    column_span: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    coordinate: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    extracted_table: Mapped[ExtractedTable] = relationship(
        back_populates="cells",
        foreign_keys=[extracted_table_id],
    )
