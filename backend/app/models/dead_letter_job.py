"""Secret-free dead-letter record for exhausted background work."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import DeadLetterStatus, enum_values


class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"
    __table_args__ = (
        Index("ix_dead_letter_jobs_status", "status"),
        Index("ix_dead_letter_jobs_task_name", "task_name"),
        Index("ix_dead_letter_jobs_last_failed", "last_failed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    maximum_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    last_error: Mapped[str] = mapped_column(Text, nullable=False)
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    retry_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    sanitized_arguments_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    status: Mapped[DeadLetterStatus] = mapped_column(
        Enum(
            DeadLetterStatus,
            name="dead_letter_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=DeadLetterStatus.ACTIVE,
        server_default=DeadLetterStatus.ACTIVE.value,
    )
    dismissed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    dismissal_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
