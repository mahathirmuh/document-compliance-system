"""Canonical document-section definitions within an alias profile."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.detected_section import DetectedSection
    from app.models.section_alias import SectionAlias
    from app.models.section_alias_profile import SectionAliasProfile
    from app.models.user import User


DEFAULT_CANONICAL_SECTION_CODES = (
    "TITLE",
    "PURPOSE",
    "SCOPE",
    "DEFINITION",
    "REFERENCE",
    "RESPONSIBILITY",
    "PROCEDURE",
    "RECORDS",
    "ATTACHMENT",
    "REVISION_HISTORY",
    "APPROVAL",
    "DISTRIBUTION",
)
_CANONICAL_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SectionDefinition(Base):
    """A language-neutral section used by compliance validation."""

    __tablename__ = "section_definitions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "canonical_code",
            name="uq_section_definitions_profile_code",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="section_definitions_display_order_nonnegative",
        ),
        Index("ix_section_definitions_profile_id", "profile_id"),
        Index("ix_section_definitions_canonical_code", "canonical_code"),
        Index("ix_section_definitions_display_order", "display_order"),
        Index("ix_section_definitions_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("section_alias_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_required_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_repeatable: Mapped[bool] = mapped_column(
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

    profile: Mapped[SectionAliasProfile] = relationship(
        back_populates="definitions",
        foreign_keys=[profile_id],
    )
    aliases: Mapped[list[SectionAlias]] = relationship(
        back_populates="section_definition",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SectionAlias.priority.desc()",
    )
    detected_sections: Mapped[list[DetectedSection]] = relationship(
        back_populates="section_definition",
        passive_deletes=True,
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])

    @validates("canonical_code")
    def normalize_canonical_code(self, _: str, value: str) -> str:
        normalized = value.strip().upper()
        if not _CANONICAL_CODE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Canonical section code must contain uppercase letters, "
                "numbers, or underscores."
            )
        return normalized

    @validates("display_name")
    def normalize_display_name(self, _: str, value: str) -> str:
        return value.strip()
