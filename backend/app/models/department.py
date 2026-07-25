"""Department master-data persistence model."""

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
    from app.models.document import Document
    from app.models.section import Section
    from app.models.user import User


class Department(Base):
    """An organizational department available to users and sections."""

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("code", name="uq_departments_code"),
        Index("ix_departments_code", "code"),
        Index("ix_departments_name", "name"),
        Index("ix_departments_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    sections: Mapped[list[Section]] = relationship(
        back_populates="department",
        passive_deletes=True,
    )
    users: Mapped[list[User]] = relationship(
        back_populates="department",
        foreign_keys="User.department_id",
        passive_deletes=True,
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="department",
        foreign_keys="Document.department_id",
        passive_deletes=True,
    )
    owned_documents: Mapped[list[Document]] = relationship(
        back_populates="owner_department",
        foreign_keys="Document.owner_department_id",
        passive_deletes=True,
    )
    creator: Mapped[User | None] = relationship(
        foreign_keys=[created_by],
    )
    updater: Mapped[User | None] = relationship(
        foreign_keys=[updated_by],
    )

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("name")
    def normalize_name(self, _: str, value: str) -> str:
        return value.strip()
