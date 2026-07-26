"""Manually executable Phase 9 report schedule configurations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.report_snapshot import (
    AdvancedReportType,
    report_enum_values,
)


class ReportScheduleType(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM_CRON = "CUSTOM_CRON"


class ReportSchedule(Base):
    """Configuration only; Phase 9 intentionally has no email delivery."""

    __tablename__ = "report_schedules"
    __table_args__ = (
        Index("ix_report_schedules_report_type", "report_type"),
        Index("ix_report_schedules_is_active", "is_active"),
        Index(
            "ix_report_schedules_scope_department_id",
            "scope_department_id",
        ),
        Index("ix_report_schedules_next_run_at", "next_run_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    report_type: Mapped[AdvancedReportType] = mapped_column(
        Enum(
            AdvancedReportType,
            name="advanced_report_type",
            values_callable=report_enum_values,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    filters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    formats_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    schedule_type: Mapped[ReportScheduleType] = mapped_column(
        Enum(
            ReportScheduleType,
            name="report_schedule_type",
            values_callable=report_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    cron_expression: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Asia/Makassar"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    scope_department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
