"""Language-specific glossary translations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.glossary_enums import GlossaryLanguageCode, enum_values

if TYPE_CHECKING:
    from app.models.glossary_term import GlossaryTerm
    from app.models.glossary_term_variant import GlossaryTermVariant


class GlossaryTranslation(Base):
    """One approved or disallowed term form in ID, EN, or ZH."""

    __tablename__ = "glossary_translations"
    __table_args__ = (
        UniqueConstraint(
            "glossary_term_id",
            "language_code",
            "normalised_term",
            name="uq_glossary_translations_term_language_normalised",
        ),
        CheckConstraint(
            "priority >= 0",
            name="glossary_translations_priority_nonnegative",
        ),
        Index(
            "ix_glossary_translations_glossary_term_id",
            "glossary_term_id",
        ),
        Index("ix_glossary_translations_language_code", "language_code"),
        Index("ix_glossary_translations_normalised_term", "normalised_term"),
        Index("ix_glossary_translations_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    glossary_term_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_terms.id", ondelete="CASCADE"),
        nullable=False,
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
    term_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalised_term: Mapped[str] = mapped_column(String(500), nullable=False)
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
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    usage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    term: Mapped[GlossaryTerm] = relationship(
        back_populates="translations",
        foreign_keys=[glossary_term_id],
    )
    variants: Mapped[list[GlossaryTermVariant]] = relationship(
        back_populates="translation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
