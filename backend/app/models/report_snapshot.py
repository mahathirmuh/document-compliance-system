"""Private advanced-report artifacts and their durable job lifecycle."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
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


class AdvancedReportType(StrEnum):
    COMPLIANCE_OVERVIEW = "COMPLIANCE_OVERVIEW"
    FINDINGS_ANALYTICS = "FINDINGS_ANALYTICS"
    TRANSLATION_SIMILARITY = "TRANSLATION_SIMILARITY"
    GLOSSARY_COMPLIANCE = "GLOSSARY_COMPLIANCE"
    REVISION_CHANGES = "REVISION_CHANGES"
    DEPARTMENT_PERFORMANCE = "DEPARTMENT_PERFORMANCE"
    DOCUMENT_TYPE_PERFORMANCE = "DOCUMENT_TYPE_PERFORMANCE"
    VALIDATION_RULE_PERFORMANCE = "VALIDATION_RULE_PERFORMANCE"
    LANGUAGE_QUALITY = "LANGUAGE_QUALITY"
    PROCESSING_PERFORMANCE = "PROCESSING_PERFORMANCE"


class ReportFileFormat(StrEnum):
    XLSX = "xlsx"
    JSON = "json"
    PDF = "pdf"


class ReportSnapshotStatus(StrEnum):
    GENERATING = "GENERATING"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class ReportJobStatus(StrEnum):
    QUEUED = "QUEUED"
    BUILDING_DATASET = "BUILDING_DATASET"
    GENERATING_CHARTS = "GENERATING_CHARTS"
    CREATING_FILE = "CREATING_FILE"
    STORING_FILE = "STORING_FILE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


def report_enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ReportSnapshot(Base):
    """One authenticated, expiring report artifact."""

    __tablename__ = "report_snapshots"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="report_snapshots_progress_range",
        ),
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="report_snapshots_file_size_nonnegative",
        ),
        CheckConstraint(
            "dataset_hash IS NULL OR length(dataset_hash) = 64",
            name="report_snapshots_dataset_hash_length",
        ),
        Index("ix_report_snapshots_report_type", "report_type"),
        Index("ix_report_snapshots_status", "status"),
        Index("ix_report_snapshots_job_status", "job_status"),
        Index("ix_report_snapshots_generated_by", "generated_by"),
        Index(
            "ix_report_snapshots_scope_department_id",
            "scope_department_id",
        ),
        Index("ix_report_snapshots_generated_at", "generated_at"),
        Index("ix_report_snapshots_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    report_type: Mapped[AdvancedReportType] = mapped_column(
        Enum(
            AdvancedReportType,
            name="advanced_report_type",
            values_callable=report_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    report_name: Mapped[str] = mapped_column(String(300), nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    dataset_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status: Mapped[ReportSnapshotStatus] = mapped_column(
        Enum(
            ReportSnapshotStatus,
            name="report_snapshot_status",
            values_callable=report_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ReportSnapshotStatus.GENERATING,
        server_default=ReportSnapshotStatus.GENERATING.value,
    )
    job_status: Mapped[ReportJobStatus] = mapped_column(
        Enum(
            ReportJobStatus,
            name="report_job_status",
            values_callable=report_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ReportJobStatus.QUEUED,
        server_default=ReportJobStatus.QUEUED.value,
    )
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    generated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope_department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_format: Mapped[ReportFileFormat] = mapped_column(
        Enum(
            ReportFileFormat,
            name="report_file_format",
            values_callable=report_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
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
