"""Multilingual aliases used to match headings to canonical sections."""

from __future__ import annotations

import re
import unicodedata
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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.section_definition import SectionDefinition
    from app.models.user import User

_NUMBERING_PATTERN = re.compile(
    r"^\s*(?:"
    r"(?:\d+(?:\.\d+)*)"
    r"|(?:[A-Za-z])"
    r"|(?:[IVXLCDMivxlcdm]+)"
    r"|(?:[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d"
    r"\u4e03\u516b\u4e5d\u5341\u767e\u5343]+)"
    r")[\s.)\-\u3001\uff0e:]+"
)
_TRAILING_PUNCTUATION_PATTERN = re.compile(r"[\s:：\-–—]+$")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalise_section_heading(value: str) -> str:
    """Normalise a literal heading while preserving Han characters."""
    normalized = unicodedata.normalize("NFC", value).strip()
    normalized = _NUMBERING_PATTERN.sub("", normalized)
    normalized = _TRAILING_PUNCTUATION_PATTERN.sub("", normalized)
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.casefold()


class SectionAlias(Base):
    """One language-specific way to write a canonical section heading."""

    __tablename__ = "section_aliases"
    __table_args__ = (
        UniqueConstraint(
            "section_definition_id",
            "language_code",
            "normalised_alias",
            name="uq_section_aliases_definition_language_normalised",
        ),
        CheckConstraint(
            "priority >= 0",
            name="section_aliases_priority_nonnegative",
        ),
        Index(
            "ix_section_aliases_section_definition_id",
            "section_definition_id",
        ),
        Index("ix_section_aliases_language_code", "language_code"),
        Index("ix_section_aliases_normalised_alias", "normalised_alias"),
        Index("ix_section_aliases_match_type", "match_type"),
        Index("ix_section_aliases_priority", "priority"),
        Index("ix_section_aliases_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    section_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("section_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    language_code: Mapped[SectionAliasLanguageCode] = mapped_column(
        Enum(
            SectionAliasLanguageCode,
            name="section_alias_language_code",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalised_alias: Mapped[str] = mapped_column(Text, nullable=False)
    match_type: Mapped[SectionAliasMatchType] = mapped_column(
        Enum(
            SectionAliasMatchType,
            name="section_alias_match_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SectionAliasMatchType.EXACT,
        server_default=SectionAliasMatchType.EXACT.value,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
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

    section_definition: Mapped[SectionDefinition] = relationship(
        back_populates="aliases",
        foreign_keys=[section_definition_id],
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])

    @validates("alias_text")
    def normalize_alias_text(self, _: str, value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).strip()
        if not normalized:
            raise ValueError("Section alias text must not be empty.")
        return normalized

    @validates("normalised_alias")
    def validate_normalised_alias(self, _: str, value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).strip()
        if not normalized:
            raise ValueError("Normalised section alias must not be empty.")
        return normalized
