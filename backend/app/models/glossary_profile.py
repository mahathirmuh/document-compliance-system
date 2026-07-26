"""Scoped glossary profiles introduced in Phase 9."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.glossary_enums import GlossaryScopeType, enum_values

if TYPE_CHECKING:
    from app.models.glossary_term import GlossaryTerm


class GlossaryProfile(Base):
    """One versioned glossary configuration at a bounded business scope."""

    __tablename__ = "glossary_profiles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_glossary_profiles_code"),
        CheckConstraint(
            "(scope_type = 'GLOBAL' "
            "AND department_id IS NULL AND document_type_id IS NULL) "
            "OR (scope_type = 'DEPARTMENT' "
            "AND department_id IS NOT NULL AND document_type_id IS NULL) "
            "OR (scope_type = 'DOCUMENT_TYPE' "
            "AND department_id IS NULL AND document_type_id IS NOT NULL) "
            "OR (scope_type = 'DEPARTMENT_DOCUMENT_TYPE' "
            "AND department_id IS NOT NULL "
            "AND document_type_id IS NOT NULL)",
            name="glossary_profiles_scope_consistent",
        ),
        CheckConstraint(
            "version >= 1",
            name="glossary_profiles_version_positive",
        ),
        Index("ix_glossary_profiles_scope_type", "scope_type"),
        Index("ix_glossary_profiles_department_id", "department_id"),
        Index("ix_glossary_profiles_document_type_id", "document_type_id"),
        Index("ix_glossary_profiles_is_default", "is_default"),
        Index("ix_glossary_profiles_is_active", "is_active"),
        Index(
            "ix_glossary_profiles_scope_resolution",
            "department_id",
            "document_type_id",
            "is_active",
            "is_default",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_type: Mapped[GlossaryScopeType] = mapped_column(
        Enum(
            GlossaryScopeType,
            name="glossary_scope_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GlossaryScopeType.GLOBAL,
        server_default=GlossaryScopeType.GLOBAL.value,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=True,
    )
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
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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

    terms: Mapped[list[GlossaryTerm]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GlossaryTerm.term_code",
    )

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Glossary profile code is required.")
        return normalized
