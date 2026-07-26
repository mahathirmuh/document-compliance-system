"""Approved, scoped retention rules for operational data."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import enum_values


class RetentionEntityType(StrEnum):
    TEMP_UPLOAD = "TEMP_UPLOAD"
    REPORT_SNAPSHOT = "REPORT_SNAPSHOT"
    JOB_LOG = "JOB_LOG"
    NOTIFICATION = "NOTIFICATION"
    AUDIT_LOG = "AUDIT_LOG"
    DELETED_FILE = "DELETED_FILE"
    EXTRACTION_HISTORY = "EXTRACTION_HISTORY"
    OCR_HISTORY = "OCR_HISTORY"
    SYNC_HISTORY = "SYNC_HISTORY"
    WEBHOOK_EVENT = "WEBHOOK_EVENT"


class RetentionScopeType(StrEnum):
    GLOBAL = "GLOBAL"
    DEPARTMENT = "DEPARTMENT"
    DOCUMENT_TYPE = "DOCUMENT_TYPE"
    DEPARTMENT_DOCUMENT_TYPE = "DEPARTMENT_DOCUMENT_TYPE"


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"
    __table_args__ = (
        CheckConstraint(
            "retention_days >= 1 AND "
            "(archive_after_days IS NULL OR archive_after_days >= 1) AND "
            "(delete_after_days IS NULL OR delete_after_days >= 1) AND "
            "(archive_after_days IS NULL OR delete_after_days IS NULL "
            "OR delete_after_days >= archive_after_days)",
            name="data_retention_policies_day_ranges",
        ),
        CheckConstraint(
            "(scope_type = 'GLOBAL' AND department_id IS NULL "
            "AND document_type_id IS NULL) OR "
            "(scope_type = 'DEPARTMENT' AND department_id IS NOT NULL "
            "AND document_type_id IS NULL) OR "
            "(scope_type = 'DOCUMENT_TYPE' AND department_id IS NULL "
            "AND document_type_id IS NOT NULL) OR "
            "(scope_type = 'DEPARTMENT_DOCUMENT_TYPE' "
            "AND department_id IS NOT NULL "
            "AND document_type_id IS NOT NULL)",
            name="data_retention_policies_scope_consistent",
        ),
        Index("ix_data_retention_policies_entity_type", "entity_type"),
        Index("ix_data_retention_policies_department_id", "department_id"),
        Index(
            "ix_data_retention_policies_document_type_id",
            "document_type_id",
        ),
        Index("ix_data_retention_policies_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[RetentionEntityType] = mapped_column(
        Enum(
            RetentionEntityType,
            name="retention_entity_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    scope_type: Mapped[RetentionScopeType] = mapped_column(
        Enum(
            RetentionScopeType,
            name="retention_scope_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RetentionScopeType.GLOBAL,
        server_default=RetentionScopeType.GLOBAL.value,
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
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delete_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_hold_enabled: Mapped[bool] = mapped_column(
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
