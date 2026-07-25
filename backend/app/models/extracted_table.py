"""Structured table metadata retained alongside unified blocks."""

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
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.extracted_container import ExtractedContainer
    from app.models.extracted_table_cell import ExtractedTableCell
    from app.models.extraction_run import ExtractionRun


class ExtractedTable(Base):
    """One DOCX, XLSX, or confidently detected PDF table."""

    __tablename__ = "extracted_tables"
    __table_args__ = (
        CheckConstraint(
            "table_index >= 0",
            name="table_index_nonnegative",
        ),
        CheckConstraint(
            "row_count >= 0 AND column_count >= 0",
            name="dimensions_nonnegative",
        ),
        Index(
            "ix_extracted_tables_extraction_run_id",
            "extraction_run_id",
        ),
        Index("ix_extracted_tables_container_id", "container_id"),
        Index("ix_extracted_tables_table_index", "table_index"),
        Index(
            "ix_extracted_tables_source_reference",
            "source_reference",
        ),
        Index(
            "ix_extracted_tables_run_order",
            "extraction_run_id",
            "container_id",
            "table_index",
        ),
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
    source_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    raw_text: Mapped[str] = mapped_column(
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

    extraction_run: Mapped[ExtractionRun] = relationship(
        back_populates="tables",
        foreign_keys=[extraction_run_id],
    )
    container: Mapped[ExtractedContainer] = relationship(
        back_populates="tables",
        foreign_keys=[container_id],
    )
    cells: Mapped[list[ExtractedTableCell]] = relationship(
        back_populates="extracted_table",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "ExtractedTableCell.row_index, "
            "ExtractedTableCell.column_index"
        ),
    )
