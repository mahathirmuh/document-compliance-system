"""Retained glossary term occurrences with source provenance."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.glossary_enums import (
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossarySourceType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.glossary_exception import GlossaryException
    from app.models.glossary_term import GlossaryTerm
    from app.models.glossary_term_variant import GlossaryTermVariant
    from app.models.glossary_translation import GlossaryTranslation
    from app.models.glossary_validation_run import GlossaryValidationRun


class GlossaryMatch(Base):
    """One bounded match; no full document content is retained here."""

    __tablename__ = "glossary_matches"
    __table_args__ = (
        CheckConstraint(
            "start_offset >= 0 AND end_offset >= start_offset",
            name="glossary_matches_offset_range",
        ),
        CheckConstraint(
            "(source_type = 'NATIVE_EXTRACTION' "
            "AND extracted_block_id IS NOT NULL) "
            "OR (source_type = 'OCR' AND ocr_block_id IS NOT NULL)",
            name="glossary_matches_source_consistent",
        ),
        Index(
            "ix_glossary_matches_validation_run_id",
            "glossary_validation_run_id",
        ),
        Index("ix_glossary_matches_glossary_term_id", "glossary_term_id"),
        Index(
            "ix_glossary_matches_glossary_translation_id",
            "glossary_translation_id",
        ),
        Index("ix_glossary_matches_glossary_variant_id", "glossary_variant_id"),
        Index("ix_glossary_matches_language_code", "language_code"),
        Index("ix_glossary_matches_container_id", "container_id"),
        Index("ix_glossary_matches_detected_section_id", "detected_section_id"),
        Index("ix_glossary_matches_exception_id", "exception_id"),
        Index("ix_glossary_matches_match_type", "match_type"),
        Index("ix_glossary_matches_is_forbidden", "is_forbidden"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    glossary_validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    glossary_term_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_terms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    glossary_translation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_translations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    glossary_variant_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_term_variants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_code: Mapped[GlossaryLanguageCode] = mapped_column(
        Enum(
            GlossaryLanguageCode,
            name="glossary_language_code",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_type: Mapped[GlossarySourceType] = mapped_column(
        Enum(
            GlossarySourceType,
            name="glossary_source_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
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
    detected_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    matched_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalised_matched_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    match_type: Mapped[GlossaryMatchType] = mapped_column(
        Enum(
            GlossaryMatchType,
            name="glossary_match_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_preferred: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_forbidden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    exception_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_exceptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    validation_run: Mapped[GlossaryValidationRun] = relationship(
        back_populates="matches",
        foreign_keys=[glossary_validation_run_id],
    )
    term: Mapped[GlossaryTerm] = relationship(
        foreign_keys=[glossary_term_id]
    )
    translation: Mapped[GlossaryTranslation | None] = relationship(
        foreign_keys=[glossary_translation_id]
    )
    variant: Mapped[GlossaryTermVariant | None] = relationship(
        foreign_keys=[glossary_variant_id]
    )
    exception: Mapped[GlossaryException | None] = relationship(
        foreign_keys=[exception_id]
    )
