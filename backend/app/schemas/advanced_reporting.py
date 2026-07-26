"""Strict contracts for Phase 9 advanced reporting."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.report_schedule import ReportScheduleType
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshotStatus,
)
from app.schemas.base import ApiSchema


class AdvancedReportFilters(ApiSchema):
    date_from: date | None = None
    date_to: date | None = None
    department_ids: list[UUID] = Field(default_factory=list, max_length=500)
    section_ids: list[UUID] = Field(default_factory=list, max_length=500)
    document_type_ids: list[UUID] = Field(
        default_factory=list, max_length=500
    )
    document_status_ids: list[UUID] = Field(
        default_factory=list, max_length=500
    )
    validation_rule_ids: list[UUID] = Field(
        default_factory=list, max_length=500
    )
    compliance_statuses: list[str] = Field(
        default_factory=list, max_length=20
    )
    finding_severities: list[str] = Field(
        default_factory=list, max_length=20
    )
    finding_statuses: list[str] = Field(default_factory=list, max_length=20)
    language_pairs: list[str] = Field(default_factory=list, max_length=10)
    glossary_profile_ids: list[UUID] = Field(
        default_factory=list, max_length=500
    )
    revision_range: list[str] = Field(default_factory=list, max_length=2)
    include_archived: bool = False

    @model_validator(mode="after")
    def valid_date_range(self) -> AdvancedReportFilters:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_to < self.date_from
        ):
            raise ValueError("dateTo must be on or after dateFrom.")
        return self


class AdvancedReportGenerateRequest(ApiSchema):
    report_type: AdvancedReportType
    report_name: str = Field(min_length=1, max_length=300)
    filters: AdvancedReportFilters = Field(
        default_factory=AdvancedReportFilters
    )
    output_format: ReportFileFormat
    include_charts: bool = True
    include_detailed_tables: bool = True

    @field_validator("report_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reportName must contain visible characters.")
        return normalized


class AdvancedReportJobResponse(ApiSchema):
    id: UUID
    report_type: AdvancedReportType
    report_name: str
    output_format: ReportFileFormat
    status: ReportJobStatus
    snapshot_status: ReportSnapshotStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None


class AdvancedReportJobListResponse(ApiSchema):
    items: list[AdvancedReportJobResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReportSnapshotResponse(ApiSchema):
    id: UUID
    report_type: AdvancedReportType
    report_name: str
    filters: dict[str, object]
    dataset_hash: str | None
    status: ReportSnapshotStatus
    job_status: ReportJobStatus
    generated_by: UUID | None
    generated_at: datetime | None
    file_format: ReportFileFormat
    file_size: int | None
    expires_at: datetime | None
    metadata: dict[str, object]
    created_at: datetime


class ReportSnapshotListResponse(ApiSchema):
    items: list[ReportSnapshotResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReportScheduleCreateRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=300)
    report_type: AdvancedReportType
    filters: AdvancedReportFilters = Field(
        default_factory=AdvancedReportFilters
    )
    formats: list[ReportFileFormat] = Field(min_length=1, max_length=3)
    schedule_type: ReportScheduleType
    cron_expression: str | None = Field(default=None, max_length=200)
    timezone: str = Field(default="Asia/Makassar", min_length=1, max_length=100)

    @field_validator("name", "timezone")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("The value must contain visible characters.")
        return normalized

    @field_validator("formats")
    @classmethod
    def unique_formats(
        cls, value: list[ReportFileFormat]
    ) -> list[ReportFileFormat]:
        if len(set(value)) != len(value):
            raise ValueError("formats must not contain duplicates.")
        return value


class ReportScheduleUpdateRequest(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    report_type: AdvancedReportType | None = None
    filters: AdvancedReportFilters | None = None
    formats: list[ReportFileFormat] | None = Field(
        default=None, min_length=1, max_length=3
    )
    schedule_type: ReportScheduleType | None = None
    cron_expression: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

    @field_validator("name", "timezone")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("The value must contain visible characters.")
        return normalized

    @field_validator("formats")
    @classmethod
    def unique_optional_formats(
        cls, value: list[ReportFileFormat] | None
    ) -> list[ReportFileFormat] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("formats must not contain duplicates.")
        return value


class ReportScheduleResponse(ApiSchema):
    id: UUID
    name: str
    report_type: AdvancedReportType
    filters: dict[str, object]
    formats: list[ReportFileFormat]
    schedule_type: ReportScheduleType
    cron_expression: str | None
    timezone: str
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ReportScheduleListResponse(ApiSchema):
    items: list[ReportScheduleResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReportScheduleRunResponse(ApiSchema):
    schedule_id: UUID
    job_ids: list[UUID]


class ReportSnapshotDeleteResponse(ApiSchema):
    snapshot_id: UUID
    status: ReportSnapshotStatus
