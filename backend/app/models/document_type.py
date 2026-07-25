"""Document-type master-data persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User
    from app.models.validation_rule import ValidationRule


DOCUMENT_TYPE_CATEGORIES = (
    "PROCEDURE",
    "POLICY",
    "GUIDELINE",
    "FORM",
    "MANUAL",
    "PLAN",
    "OTHER",
)


class DocumentType(Base):
    """A controlled document classification."""

    __tablename__ = "document_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_document_types_code"),
        CheckConstraint(
            "category IS NULL OR category IN "
            "('PROCEDURE','POLICY','GUIDELINE','FORM','MANUAL','PLAN','OTHER')",
            name="document_types_category",
        ),
        Index("ix_document_types_code", "code"),
        Index("ix_document_types_name", "name"),
        Index("ix_document_types_category", "category"),
        Index("ix_document_types_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_section: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    default_validation_rule_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "validation_rules.id",
            name=(
                "fk_document_types_default_validation_rule_id_"
                "validation_rules"
            ),
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    validation_rules: Mapped[list[ValidationRule]] = relationship(
        back_populates="document_type",
        foreign_keys="ValidationRule.document_type_id",
        passive_deletes=True,
    )
    default_validation_rule: Mapped[ValidationRule | None] = relationship(
        foreign_keys=[default_validation_rule_id],
        post_update=True,
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])
    documents: Mapped[list[Document]] = relationship(
        back_populates="document_type",
        foreign_keys="Document.document_type_id",
        passive_deletes=True,
    )

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("name")
    def normalize_name(self, _: str, value: str) -> str:
        return value.strip()

    @validates("category")
    def normalize_category(self, _: str, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None
