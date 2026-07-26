"""Audited, bounded glossary validation exceptions."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.glossary_enums import (
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.glossary_term import GlossaryTerm


class GlossaryException(Base):
    """A reasoned exception that never mutates source documents."""

    __tablename__ = "glossary_exceptions"
    __table_args__ = (
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="glossary_exceptions_reason_required",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL "
            "OR effective_to >= effective_from",
            name="glossary_exceptions_effective_range",
        ),
        CheckConstraint(
            "(scope_type = 'GLOBAL' AND department_id IS NULL "
            "AND document_id IS NULL AND document_revision_id IS NULL "
            "AND document_file_id IS NULL "
            "AND section_definition_id IS NULL) "
            "OR (scope_type = 'DEPARTMENT' "
            "AND department_id IS NOT NULL) "
            "OR (scope_type = 'DOCUMENT' AND document_id IS NOT NULL) "
            "OR (scope_type = 'DOCUMENT_REVISION' "
            "AND document_revision_id IS NOT NULL) "
            "OR (scope_type = 'DOCUMENT_FILE' "
            "AND document_file_id IS NOT NULL) "
            "OR (scope_type = 'SECTION' "
            "AND section_definition_id IS NOT NULL)",
            name="glossary_exceptions_scope_target_required",
        ),
        Index("ix_glossary_exceptions_glossary_term_id", "glossary_term_id"),
        Index("ix_glossary_exceptions_scope_type", "scope_type"),
        Index("ix_glossary_exceptions_department_id", "department_id"),
        Index("ix_glossary_exceptions_document_id", "document_id"),
        Index(
            "ix_glossary_exceptions_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_glossary_exceptions_document_file_id", "document_file_id"),
        Index(
            "ix_glossary_exceptions_section_definition_id",
            "section_definition_id",
        ),
        Index("ix_glossary_exceptions_effective_to", "effective_to"),
        Index("ix_glossary_exceptions_is_active", "is_active"),
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
    scope_type: Mapped[GlossaryExceptionScopeType] = mapped_column(
        Enum(
            GlossaryExceptionScopeType,
            name="glossary_exception_scope_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="RESTRICT"),
        nullable=True,
    )
    section_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("section_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_code: Mapped[GlossaryLanguageCode | None] = mapped_column(
        Enum(
            GlossaryLanguageCode,
            name="glossary_language_code",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    exception_type: Mapped[GlossaryExceptionType] = mapped_column(
        Enum(
            GlossaryExceptionType,
            name="glossary_exception_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
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

    term: Mapped[GlossaryTerm] = relationship(
        back_populates="exceptions",
        foreign_keys=[glossary_term_id],
    )

    @validates("reason")
    def normalize_reason(self, _: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Glossary exception reason is required.")
        return normalized
