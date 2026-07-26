"""Glossary concepts introduced in Phase 9."""

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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.glossary_enums import (
    GlossaryTermSeverity,
    GlossaryTermType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.glossary_exception import GlossaryException
    from app.models.glossary_profile import GlossaryProfile
    from app.models.glossary_translation import GlossaryTranslation


class GlossaryTerm(Base):
    """One multilingual concept and its matching policy."""

    __tablename__ = "glossary_terms"
    __table_args__ = (
        UniqueConstraint(
            "glossary_profile_id",
            "term_code",
            name="uq_glossary_terms_profile_code",
        ),
        Index(
            "ix_glossary_terms_glossary_profile_id",
            "glossary_profile_id",
        ),
        Index("ix_glossary_terms_term_code", "term_code"),
        Index("ix_glossary_terms_concept_name", "concept_name"),
        Index("ix_glossary_terms_term_type", "term_type"),
        Index("ix_glossary_terms_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    glossary_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_code: Mapped[str] = mapped_column(String(100), nullable=False)
    concept_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    term_type: Mapped[GlossaryTermType] = mapped_column(
        Enum(
            GlossaryTermType,
            name="glossary_term_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GlossaryTermType.PREFERRED,
        server_default=GlossaryTermType.PREFERRED.value,
    )
    severity: Mapped[GlossaryTermSeverity] = mapped_column(
        Enum(
            GlossaryTermSeverity,
            name="glossary_term_severity",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GlossaryTermSeverity.MINOR,
        server_default=GlossaryTermSeverity.MINOR.value,
    )
    is_case_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    match_whole_word: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    allow_inflection: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_regex: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    profile: Mapped[GlossaryProfile] = relationship(
        back_populates="terms",
        foreign_keys=[glossary_profile_id],
    )
    translations: Mapped[list[GlossaryTranslation]] = relationship(
        back_populates="term",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GlossaryTranslation.priority",
    )
    exceptions: Mapped[list[GlossaryException]] = relationship(
        back_populates="term",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("term_code")
    def normalize_term_code(self, _: str, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Glossary term code is required.")
        return normalized
