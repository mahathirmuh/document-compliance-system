"""Document revision persistence for the Phase 4 register."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_status import DocumentStatus
    from app.models.user import User
    from app.models.validation_rule import ValidationRule


class DocumentRevision(Base):
    """One version of a stable document identity."""

    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "revision_code",
            name="uq_document_revisions_document_id_revision_code",
        ),
        UniqueConstraint(
            "full_document_code",
            name="uq_document_revisions_full_document_code",
        ),
        CheckConstraint(
            "revision_number IS NULL OR revision_number >= 0",
            name="revision_number_nonnegative",
        ),
        CheckConstraint(
            "expiry_date IS NULL OR effective_date IS NULL "
            "OR expiry_date >= effective_date",
            name="expiry_after_effective",
        ),
        CheckConstraint(
            "review_date IS NULL OR issue_date IS NULL "
            "OR review_date >= issue_date",
            name="review_after_issue",
        ),
        CheckConstraint(
            "superseded_by_revision_id IS NULL "
            "OR superseded_by_revision_id <> id",
            name="not_self_superseded",
        ),
        Index("ix_document_revisions_document_id", "document_id"),
        Index("ix_document_revisions_revision_code", "revision_code"),
        Index(
            "ix_document_revisions_document_status_id",
            "document_status_id",
        ),
        Index(
            "ix_document_revisions_validation_rule_id",
            "validation_rule_id",
        ),
        Index("ix_document_revisions_is_current", "is_current"),
        Index("ix_document_revisions_effective_date", "effective_date"),
        Index("ix_document_revisions_created_at", "created_at"),
        Index(
            "uq_document_revisions_one_current",
            "document_id",
            unique=True,
            postgresql_where=text(
                "is_current IS TRUE AND deleted_at IS NULL"
            ),
            sqlite_where=text("is_current = 1 AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_code: Mapped[str] = mapped_column(String(30), nullable=False)
    revision_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    full_document_code: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    document_status_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_statuses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_rule_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sharepoint_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_superseded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    superseded_by_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "document_revisions.id",
            name="fk_doc_revisions_superseded_by",
            ondelete="SET NULL",
        ),
        nullable=True,
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

    document: Mapped[Document] = relationship(
        back_populates="revisions",
        foreign_keys=[document_id],
    )
    document_status: Mapped[DocumentStatus] = relationship(
        back_populates="document_revisions",
        foreign_keys=[document_status_id],
    )
    validation_rule: Mapped[ValidationRule | None] = relationship(
        back_populates="document_revisions",
        foreign_keys=[validation_rule_id],
    )
    superseded_by_revision: Mapped[DocumentRevision | None] = relationship(
        remote_side=[id],
        foreign_keys=[superseded_by_revision_id],
    )
    creator: Mapped[User | None] = relationship(
        back_populates="created_document_revisions",
        foreign_keys=[created_by],
    )
    updater: Mapped[User | None] = relationship(
        back_populates="updated_document_revisions",
        foreign_keys=[updated_by],
    )

    @validates("revision_code")
    def normalize_revision(self, _: str, value: str) -> str:
        return value.strip()

    @validates("full_document_code")
    def normalize_full_code(self, _: str, value: str) -> str:
        return value.strip()
