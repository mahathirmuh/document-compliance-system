"""Approved and forbidden glossary variants."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.glossary_enums import GlossaryVariantType, enum_values

if TYPE_CHECKING:
    from app.models.glossary_translation import GlossaryTranslation


class GlossaryTermVariant(Base):
    """A synonym, abbreviation, legacy form, or forbidden spelling."""

    __tablename__ = "glossary_term_variants"
    __table_args__ = (
        UniqueConstraint(
            "glossary_translation_id",
            "normalised_variant",
            name="uq_glossary_variants_translation_normalised",
        ),
        Index(
            "ix_glossary_variants_glossary_translation_id",
            "glossary_translation_id",
        ),
        Index("ix_glossary_variants_normalised_variant", "normalised_variant"),
        Index("ix_glossary_variants_variant_type", "variant_type"),
        Index("ix_glossary_variants_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    glossary_translation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_translations.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalised_variant: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    variant_type: Mapped[GlossaryVariantType] = mapped_column(
        Enum(
            GlossaryVariantType,
            name="glossary_variant_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
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

    translation: Mapped[GlossaryTranslation] = relationship(
        back_populates="variants",
        foreign_keys=[glossary_translation_id],
    )
