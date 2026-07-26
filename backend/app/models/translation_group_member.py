"""Source-provenance members of a structural translation group."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
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

if TYPE_CHECKING:
    from app.models.extracted_block import ExtractedBlock
    from app.models.language_block_result import LanguageBlockResult
    from app.models.ocr_block import OCRBlock
    from app.models.translation_group import TranslationGroup


class TranslationGroupMember(Base):
    """A bounded snapshot and durable pointer to one source block."""

    __tablename__ = "translation_group_members"
    __table_args__ = (
        UniqueConstraint(
            "translation_group_id",
            "block_order",
            "language_code",
            name="uq_translation_group_members_group_order_language",
        ),
        CheckConstraint(
            "block_order >= 0",
            name="translation_group_members_order_nonnegative",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="translation_group_members_confidence_range",
        ),
        CheckConstraint(
            "extracted_block_id IS NOT NULL "
            "OR ocr_block_id IS NOT NULL "
            "OR language_block_result_id IS NOT NULL",
            name="translation_group_members_source_required",
        ),
        Index(
            "ix_translation_group_members_translation_group_id",
            "translation_group_id",
        ),
        Index(
            "ix_translation_group_members_extracted_block_id",
            "extracted_block_id",
        ),
        Index("ix_translation_group_members_ocr_block_id", "ocr_block_id"),
        Index(
            "ix_translation_group_members_language_block_result_id",
            "language_block_result_id",
        ),
        Index("ix_translation_group_members_language_code", "language_code"),
        Index("ix_translation_group_members_block_order", "block_order"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    translation_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_blocks.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ocr_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_blocks.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_block_result_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_block_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
    )
    position_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    translation_group: Mapped[TranslationGroup] = relationship(
        back_populates="members",
        foreign_keys=[translation_group_id],
    )
    extracted_block: Mapped[ExtractedBlock | None] = relationship(
        foreign_keys=[extracted_block_id]
    )
    ocr_block: Mapped[OCRBlock | None] = relationship(
        foreign_keys=[ocr_block_id]
    )
    language_block_result: Mapped[LanguageBlockResult | None] = relationship(
        foreign_keys=[language_block_result_id]
    )
