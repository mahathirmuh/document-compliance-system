"""Atomic OCR text blocks with geometry and provider provenance."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.ocr_page_result import OCRPageResult
    from app.models.ocr_run import OCRRun


class OCRBlock(Base):
    """One recognised text polygon, retained even at low confidence."""

    __tablename__ = "ocr_blocks"
    __table_args__ = (
        CheckConstraint(
            "block_order >= 0 AND character_count >= 0",
            name="ocr_block_counts_nonnegative",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ocr_block_confidence_range",
        ),
        CheckConstraint(
            "orientation IN (0, 90, 180, 270)",
            name="ocr_block_orientation_value",
        ),
        Index("ix_ocr_blocks_ocr_run_id", "ocr_run_id"),
        Index(
            "ix_ocr_blocks_ocr_page_result_id",
            "ocr_page_result_id",
        ),
        Index("ix_ocr_blocks_confidence", "confidence"),
        Index("ix_ocr_blocks_block_order", "block_order"),
        Index(
            "ix_ocr_blocks_page_order",
            "ocr_page_result_id",
            "block_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ocr_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    ocr_page_result_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_page_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalised_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    polygon_json: Mapped[list[list[float]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    bbox_json: Mapped[dict[str, float]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    provider_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    recognition_profile: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    orientation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ocr_run: Mapped[OCRRun] = relationship(
        back_populates="blocks",
        foreign_keys=[ocr_run_id],
    )
    page_result: Mapped[OCRPageResult] = relationship(
        back_populates="blocks",
        foreign_keys=[ocr_page_result_id],
    )

    @validates("confidence")
    def validate_confidence(self, _: str, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("OCR confidence must be between 0 and 1.")
        return value

    @validates("orientation")
    def validate_orientation(self, _: str, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("OCR orientation must be 0, 90, 180, or 270.")
        return value
