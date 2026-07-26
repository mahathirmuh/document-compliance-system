"""Named collections of multilingual canonical-section aliases."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.section_definition import SectionDefinition
    from app.models.user import User
    from app.models.validation_rule import ValidationRule


class SectionAliasProfile(Base):
    """One independently configurable section-alias namespace."""

    __tablename__ = "section_alias_profiles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_section_alias_profiles_code"),
        Index("ix_section_alias_profiles_code", "code"),
        Index("ix_section_alias_profiles_name", "name"),
        Index("ix_section_alias_profiles_is_active", "is_active"),
        Index(
            "uq_section_alias_profiles_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default IS TRUE"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(
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

    definitions: Mapped[list[SectionDefinition]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SectionDefinition.display_order",
    )
    validation_rules: Mapped[list[ValidationRule]] = relationship(
        back_populates="section_alias_profile",
        foreign_keys="ValidationRule.section_alias_profile_id",
        passive_deletes=True,
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("name")
    def normalize_name(self, _: str, value: str) -> str:
        return value.strip()
