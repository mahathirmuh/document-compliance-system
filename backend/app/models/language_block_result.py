"""Per-source-block hybrid language detection results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.language_detection_run import LanguageDetectionRun


class LanguageCode(StrEnum):
    """Phase 7 target and fallback language codes."""

    INDONESIAN = "id"
    ENGLISH = "en"
    CHINESE = "zh"
    MIXED = "mixed"
    UNKNOWN = "unknown"
    OTHER = "other"


class LanguageSourceType(StrEnum):
    """Provenance of text supplied to the detector."""

    NATIVE_EXTRACTION = "NATIVE_EXTRACTION"
    OCR = "OCR"


class LanguageEligibilityStatus(StrEnum):
    """Whether a block contains enough linguistic evidence."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class LanguageEligibilityReason(StrEnum):
    """Stable reason for not sending a block to a language model."""

    EMPTY = "EMPTY"
    TOO_SHORT = "TOO_SHORT"
    NO_LETTERS = "NO_LETTERS"
    CODE_LIKE_TEXT = "CODE_LIKE_TEXT"
    URL_ONLY = "URL_ONLY"
    EMAIL_ONLY = "EMAIL_ONLY"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class LanguageBlockResult(Base):
    """A retained decision with raw scores, script statistics, and source."""

    __tablename__ = "language_block_results"
    __table_args__ = (
        CheckConstraint(
            "(extracted_block_id IS NOT NULL AND ocr_block_id IS NULL) "
            "OR (extracted_block_id IS NULL AND ocr_block_id IS NOT NULL)",
            name="exactly_one_source_block",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        CheckConstraint(
            "character_count >= 0 AND latin_character_count >= 0 "
            "AND han_character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        CheckConstraint(
            "(eligibility_status = 'ELIGIBLE' "
            "AND eligibility_reason IS NULL) "
            "OR (eligibility_status = 'INELIGIBLE' "
            "AND eligibility_reason IS NOT NULL)",
            name="eligibility_reason_consistent",
        ),
        Index(
            "ix_language_block_results_run_id",
            "language_detection_run_id",
        ),
        Index(
            "ix_language_block_results_extracted_block_id",
            "extracted_block_id",
        ),
        Index(
            "ix_language_block_results_ocr_block_id",
            "ocr_block_id",
        ),
        Index("ix_language_block_results_container_id", "container_id"),
        Index("ix_language_block_results_source_type", "source_type"),
        Index("ix_language_block_results_language_code", "language_code"),
        Index("ix_language_block_results_confidence", "confidence"),
        Index("ix_language_block_results_is_mixed", "is_mixed"),
        Index(
            "ix_language_block_results_eligibility_status",
            "eligibility_status",
        ),
        Index(
            "ix_language_block_results_run_language",
            "language_detection_run_id",
            "language_code",
        ),
        Index(
            "ix_language_block_results_run_container",
            "language_detection_run_id",
            "container_id",
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
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[LanguageSourceType] = mapped_column(
        Enum(
            LanguageSourceType,
            name="language_source_type",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    language_code: Mapped[LanguageCode] = mapped_column(
        Enum(
            LanguageCode,
            name="language_code",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    primary_language_code: Mapped[LanguageCode] = mapped_column(
        Enum(
            LanguageCode,
            name="language_primary_code",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Numeric(6, 5),
        nullable=False,
        default=0,
        server_default="0",
    )
    is_mixed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    detected_languages_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    script_statistics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    eligibility_status: Mapped[LanguageEligibilityStatus] = mapped_column(
        Enum(
            LanguageEligibilityStatus,
            name="language_eligibility_status",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    eligibility_reason: Mapped[LanguageEligibilityReason | None] = (
        mapped_column(
            Enum(
                LanguageEligibilityReason,
                name="language_eligibility_reason",
                values_callable=_enum_values,
                validate_strings=True,
            ),
            nullable=True,
        )
    )
    character_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    latin_character_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    han_character_count: Mapped[int] = mapped_column(
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

    language_detection_run: Mapped[LanguageDetectionRun] = relationship(
        back_populates="block_results",
        foreign_keys=[language_detection_run_id],
    )
