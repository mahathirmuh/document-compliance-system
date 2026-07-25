"""Logical source containers for normalized extraction content."""

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
    from app.models.extracted_block import ExtractedBlock
    from app.models.extracted_table import ExtractedTable
    from app.models.extraction_run import ExtractionRun


class ExtractedContainerType(StrEnum):
    """Cross-format logical content container."""

    PDF_PAGE = "PDF_PAGE"
    DOCX_BODY = "DOCX_BODY"
    DOCX_HEADER = "DOCX_HEADER"
    DOCX_FOOTER = "DOCX_FOOTER"
    XLSX_WORKSHEET = "XLSX_WORKSHEET"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ExtractedContainer(Base):
    """One PDF page, DOCX part, or XLSX worksheet."""

    __tablename__ = "extracted_containers"
    _postgresql_name_search_index = Index(
        "ix_extracted_containers_name_search",
        sql_text("to_tsvector('simple', name)"),
        postgresql_using="gin",
    ).ddl_if(dialect="postgresql")

    __table_args__ = (
        CheckConstraint(
            "container_index >= 0",
            name="container_index_nonnegative",
        ),
        CheckConstraint(
            "character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        Index(
            "ix_extracted_containers_extraction_run_id",
            "extraction_run_id",
        ),
        Index(
            "ix_extracted_containers_container_type",
            "container_type",
        ),
        Index(
            "ix_extracted_containers_container_index",
            "container_index",
        ),
        Index("ix_extracted_containers_name", "name"),
        Index(
            "ix_extracted_containers_run_order",
            "extraction_run_id",
            "container_index",
        ),
        _postgresql_name_search_index,
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
    container_type: Mapped[ExtractedContainerType] = mapped_column(
        Enum(
            ExtractedContainerType,
            name="extracted_container_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    container_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str] = mapped_column(
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
        back_populates="containers",
        foreign_keys=[extraction_run_id],
    )
    blocks: Mapped[list[ExtractedBlock]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedBlock.block_order",
    )
    tables: Mapped[list[ExtractedTable]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedTable.table_index",
    )
