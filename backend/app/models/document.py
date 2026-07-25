"""Document identity persistence for the Phase 4 register."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.document_revision import DocumentRevision
    from app.models.document_type import DocumentType
    from app.models.section import Section
    from app.models.user import User


class Document(Base):
    """Stable document identity shared by all revisions."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "base_document_code",
            name="uq_documents_base_document_code",
        ),
        Index("ix_documents_company_code", "company_code"),
        Index("ix_documents_department_id", "department_id"),
        Index("ix_documents_section_id", "section_id"),
        Index("ix_documents_document_type_id", "document_type_id"),
        Index("ix_documents_document_number", "document_number"),
        Index("ix_documents_base_document_code", "base_document_code"),
        Index("ix_documents_title", "title"),
        Index("ix_documents_is_archived", "is_archived"),
        Index("ix_documents_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    company_code: Mapped[str] = mapped_column(String(20), nullable=False)
    department_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_type_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_number: Mapped[str] = mapped_column(String(50), nullable=False)
    base_document_code: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_owner_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    current_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "document_revisions.id",
            name=(
                "fk_documents_current_revision_id_document_revisions"
            ),
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    department: Mapped[Department] = relationship(
        back_populates="documents",
        foreign_keys=[department_id],
    )
    owner_department: Mapped[Department | None] = relationship(
        back_populates="owned_documents",
        foreign_keys=[owner_department_id],
    )
    section: Mapped[Section | None] = relationship(
        back_populates="documents",
        foreign_keys=[section_id],
    )
    document_type: Mapped[DocumentType] = relationship(
        back_populates="documents",
        foreign_keys=[document_type_id],
    )
    revisions: Mapped[list[DocumentRevision]] = relationship(
        back_populates="document",
        foreign_keys="DocumentRevision.document_id",
        passive_deletes=True,
        order_by="DocumentRevision.created_at",
    )
    current_revision: Mapped[DocumentRevision | None] = relationship(
        foreign_keys=[current_revision_id],
        post_update=True,
    )
    archiver: Mapped[User | None] = relationship(
        back_populates="archived_documents",
        foreign_keys=[archived_by],
    )
    creator: Mapped[User | None] = relationship(
        back_populates="created_documents",
        foreign_keys=[created_by],
    )
    updater: Mapped[User | None] = relationship(
        back_populates="updated_documents",
        foreign_keys=[updated_by],
    )

    @validates(
        "company_code",
        "document_number",
        "base_document_code",
    )
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("title")
    def normalize_title(self, _: str, value: str) -> str:
        return value.strip()

    @validates("document_owner_name")
    def normalize_owner_name(
        self,
        _: str,
        value: str | None,
    ) -> str | None:
        return value.strip() or None if value is not None else None

