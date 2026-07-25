"""Per-container preliminary language coverage summaries."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.language_detection_run import LanguageDetectionRun


class LanguageContainerSummary(Base):
    """Aggregated language counts for one extraction container."""

    __tablename__ = "language_container_summaries"
    __table_args__ = (
        UniqueConstraint(
            "language_detection_run_id",
            "container_id",
            name="uq_language_container_summaries_run_container",
        ),
        CheckConstraint(
            "container_index >= 0",
            name="container_index_nonnegative",
        ),
        CheckConstraint(
            "total_blocks >= 0 AND eligible_blocks >= 0 "
            "AND indonesian_blocks >= 0 AND english_blocks >= 0 "
            "AND chinese_blocks >= 0 AND mixed_blocks >= 0 "
            "AND unknown_blocks >= 0 AND other_blocks >= 0",
            name="block_counts_nonnegative",
        ),
        CheckConstraint(
            "eligible_blocks <= total_blocks",
            name="eligible_blocks_within_total",
        ),
        CheckConstraint(
            "indonesian_characters >= 0 AND english_characters >= 0 "
            "AND chinese_characters >= 0 AND mixed_characters >= 0 "
            "AND unknown_characters >= 0",
            name="character_counts_nonnegative",
        ),
        Index(
            "ix_language_container_summaries_run_id",
            "language_detection_run_id",
        ),
        Index(
            "ix_language_container_summaries_container_id",
            "container_id",
        ),
        Index(
            "ix_language_container_summaries_container_type",
            "container_type",
        ),
        Index(
            "ix_language_container_summaries_container_index",
            "container_index",
        ),
        Index(
            "ix_language_container_summaries_dominant_language",
            "dominant_language",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    language_detection_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    container_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    container_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    container_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    eligible_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    indonesian_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    english_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    chinese_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    mixed_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    unknown_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    other_blocks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    indonesian_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    english_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    chinese_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    mixed_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    unknown_characters: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    dominant_language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    language_presence_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    coverage_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    language_detection_run: Mapped[LanguageDetectionRun] = relationship(
        back_populates="container_summaries",
        foreign_keys=[language_detection_run_id],
    )
