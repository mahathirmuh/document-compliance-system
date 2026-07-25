"""User persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.authorization import UserRole
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.department import Department
    from app.models.document import Document
    from app.models.document_revision import DocumentRevision
    from app.models.refresh_token import RefreshToken


def _enum_values(enum_class: type[UserRole]) -> list[str]:
    """Persist enum values rather than Python member names."""
    return [member.value for member in enum_class]


class User(Base):
    """An authenticated application user.

    Users are deactivated or soft-deleted instead of being removed so that
    audit history remains attributable.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role", "role"),
        Index("ix_users_department_id", "department_id"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UserRole.VIEWER,
        server_default=UserRole.VIEWER.value,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "departments.id",
            name="fk_users_department_id_departments",
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
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
    department: Mapped[Department | None] = relationship(
        back_populates="users",
        foreign_keys=[department_id],
    )
    created_documents: Mapped[list[Document]] = relationship(
        back_populates="creator",
        foreign_keys="Document.created_by",
        passive_deletes=True,
    )
    updated_documents: Mapped[list[Document]] = relationship(
        back_populates="updater",
        foreign_keys="Document.updated_by",
        passive_deletes=True,
    )
    archived_documents: Mapped[list[Document]] = relationship(
        back_populates="archiver",
        foreign_keys="Document.archived_by",
        passive_deletes=True,
    )
    created_document_revisions: Mapped[list[DocumentRevision]] = relationship(
        back_populates="creator",
        foreign_keys="DocumentRevision.created_by",
        passive_deletes=True,
    )
    updated_document_revisions: Mapped[list[DocumentRevision]] = relationship(
        back_populates="updater",
        foreign_keys="DocumentRevision.updated_by",
        passive_deletes=True,
    )

    @validates("email")
    def normalize_email(self, _: str, value: str) -> str:
        """Persist canonical lowercase email addresses."""
        return value.strip().lower()
