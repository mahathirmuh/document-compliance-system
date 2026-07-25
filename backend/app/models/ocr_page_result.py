"""Per-page OCR output and diagnostics."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.ocr_job import OCRLanguageProfile, _enum_values

if TYPE_CHECKING:
    from app.models.ocr_block import OCRBlock
    from app.models.ocr_run import OCRRun


class OCRPageStatus(StrEnum):
    """Terminal status for one requested PDF page."""

    COMPLETED = "COMPLETED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_TEXT_FOUND = "NO_TEXT_FOUND"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class OCRPageResult(Base):
    """Rendered page geometry, text, confidence, and safe diagnostics."""

    __tablename__ = "ocr_page_results"
    __table_args__ = (
        UniqueConstraint(
            "ocr_run_id",
            "page_number",
            name="uq_ocr_page_results_run_page",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="ocr_page_result_page_positive",
        ),
        CheckConstraint(
            "render_width >= 0 AND render_height >= 0 AND render_dpi >= 72",
            name="ocr_page_result_render_dimensions",
        ),
        CheckConstraint(
            "block_count >= 0 AND character_count >= 0",
            name="ocr_page_result_counts_nonnegative",
        ),
        CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="ocr_page_result_average_confidence_range",
        ),
        CheckConstraint(
            "minimum_confidence IS NULL OR "
            "(minimum_confidence >= 0 AND minimum_confidence <= 1)",
            name="ocr_page_result_minimum_confidence_range",
        ),
        CheckConstraint(
            "maximum_confidence IS NULL OR "
            "(maximum_confidence >= 0 AND maximum_confidence <= 1)",
            name="ocr_page_result_maximum_confidence_range",
        ),
        CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="ocr_page_result_content_hash_length",
        ),
        Index("ix_ocr_page_results_ocr_run_id", "ocr_run_id"),
        Index("ix_ocr_page_results_page_number", "page_number"),
        Index("ix_ocr_page_results_status", "status"),
        Index("ix_ocr_page_results_created_at", "created_at"),
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
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OCRPageStatus] = mapped_column(
        Enum(
            OCRPageStatus,
            name="ocr_page_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    language_profile: Mapped[OCRLanguageProfile] = mapped_column(
        Enum(
            OCRLanguageProfile,
            name="ocr_language_profile",
            values_callable=_enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    render_width: Mapped[int] = mapped_column(Integer, nullable=False)
    render_height: Mapped[int] = mapped_column(Integer, nullable=False)
    render_dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation_applied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    deskew_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    block_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    average_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    minimum_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    maximum_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
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
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    warning_codes_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ocr_run: Mapped[OCRRun] = relationship(
        back_populates="pages",
        foreign_keys=[ocr_run_id],
    )
    blocks: Mapped[list[OCRBlock]] = relationship(
        back_populates="page_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OCRBlock.block_order",
    )

    @validates(
        "average_confidence",
        "minimum_confidence",
        "maximum_confidence",
    )
    def validate_confidence(
        self,
        _: str,
        value: float | None,
    ) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("OCR confidence must be between 0 and 1.")
        return value

    @validates("rotation_applied")
    def validate_rotation(self, _: str, value: int) -> int:
        if value not in {0, 90, 180, 270}:
            raise ValueError("OCR rotation must be 0, 90, 180, or 270.")
        return value
