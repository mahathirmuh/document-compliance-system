"""Multilingual validation-rule master-data persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document_revision import DocumentRevision
    from app.models.document_type import DocumentType
    from app.models.user import User


DEFAULT_LANGUAGE_ORDER = ["id", "en", "zh"]
DEFAULT_REQUIRED_SECTIONS = [
    "TITLE",
    "PURPOSE",
    "SCOPE",
    "RESPONSIBILITY",
    "PROCEDURE",
    "RECORDS",
    "REFERENCE",
]
ALLOWED_SECTION_CODES = frozenset(
    {
        "TITLE",
        "PURPOSE",
        "SCOPE",
        "DEFINITION",
        "RESPONSIBILITY",
        "PROCEDURE",
        "RECORDS",
        "REFERENCE",
        "ATTACHMENT",
        "REVISION_HISTORY",
    }
)


class ValidationRule(Base):
    """Configuration for future document-language validation."""

    __tablename__ = "validation_rules"
    __table_args__ = (
        UniqueConstraint("code", name="uq_validation_rules_code"),
        CheckConstraint(
            "minimum_indonesian_coverage BETWEEN 0 AND 100",
            name="validation_rules_indonesian_coverage",
        ),
        CheckConstraint(
            "minimum_english_coverage BETWEEN 0 AND 100",
            name="validation_rules_english_coverage",
        ),
        CheckConstraint(
            "minimum_chinese_coverage BETWEEN 0 AND 100",
            name="validation_rules_chinese_coverage",
        ),
        CheckConstraint(
            "minimum_compliance_score BETWEEN 0 AND 100",
            name="validation_rules_minimum_score",
        ),
        CheckConstraint(
            "partial_compliance_score BETWEEN 0 AND 100",
            name="validation_rules_partial_score",
        ),
        CheckConstraint(
            "partial_compliance_score <= minimum_compliance_score",
            name="validation_rules_score_order",
        ),
        CheckConstraint(
            "required_indonesian OR required_english OR required_chinese",
            name="validation_rules_language_required",
        ),
        Index("ix_validation_rules_code", "code"),
        Index("ix_validation_rules_name", "name"),
        Index("ix_validation_rules_document_type_id", "document_type_id"),
        Index("ix_validation_rules_is_active", "is_active"),
        Index(
            "uq_validation_rules_global_default",
            "is_default",
            unique=True,
            postgresql_where=text(
                "is_default IS TRUE AND document_type_id IS NULL "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "is_default = 1 AND document_type_id IS NULL "
                "AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_validation_rules_document_type_default",
            "document_type_id",
            unique=True,
            postgresql_where=text(
                "is_default IS TRUE AND document_type_id IS NOT NULL "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "is_default = 1 AND document_type_id IS NOT NULL "
                "AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=True,
    )
    required_indonesian: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    required_english: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    required_chinese: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    minimum_indonesian_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    minimum_english_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    minimum_chinese_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    validate_language_order: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    language_order_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: list(DEFAULT_LANGUAGE_ORDER),
    )
    validate_sections: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    required_sections_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: list(DEFAULT_REQUIRED_SECTIONS),
    )
    validate_tables: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    minimum_compliance_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    partial_compliance_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=70, server_default="70"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    document_type: Mapped[DocumentType | None] = relationship(
        back_populates="validation_rules",
        foreign_keys=[document_type_id],
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])
    document_revisions: Mapped[list[DocumentRevision]] = relationship(
        back_populates="validation_rule",
        foreign_keys="DocumentRevision.validation_rule_id",
        passive_deletes=True,
    )

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("name")
    def normalize_name(self, _: str, value: str) -> str:
        return value.strip()

    @validates("language_order_json", "required_sections_json")
    def copy_json_list(self, _: str, value: list[str]) -> list[str]:
        return list(value)

    def audit_values(self) -> dict[str, Any]:
        """Return JSON-safe values used by master-data audit events."""
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "documentTypeId": (
                str(self.document_type_id)
                if self.document_type_id is not None
                else None
            ),
            "isDefault": self.is_default,
            "isActive": self.is_active,
        }
