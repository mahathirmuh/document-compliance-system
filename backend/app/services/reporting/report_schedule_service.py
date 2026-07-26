"""Audited manual report schedules with safe cron configuration."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime, timedelta
from http import HTTPStatus
from math import ceil
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.report_schedule import ReportSchedule, ReportScheduleType
from app.models.report_snapshot import ReportFileFormat
from app.models.user import User
from app.repositories.report_schedule_repository import (
    ReportScheduleRepository,
)
from app.schemas.advanced_reporting import (
    AdvancedReportFilters,
    ReportScheduleCreateRequest,
    ReportScheduleListResponse,
    ReportScheduleResponse,
    ReportScheduleRunResponse,
    ReportScheduleUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import DocumentServiceBase, document_error
from app.services.reporting.advanced_reporting_service import (
    AdvancedReportingService,
)
from app.services.reporting.report_filter_service import ReportFilterService
from app.utils.datetime import utc_now

_CRON_TOKEN_RE = re.compile(r"^[0-9*/,\-]+$")
_CRON_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


class CronValidationError(ValueError):
    """Cron expression is invalid or intentionally unsupported."""


def validate_cron_expression(expression: str) -> str:
    """Validate a conservative five-field cron without executing it."""

    normalized = " ".join(expression.strip().split())
    fields = normalized.split(" ")
    if len(fields) != 5 or len(normalized) > 200:
        raise CronValidationError(
            "Cron expression must contain exactly five fields."
        )
    for field, (minimum, maximum) in zip(
        fields, _CRON_BOUNDS, strict=True
    ):
        if not _CRON_TOKEN_RE.fullmatch(field):
            raise CronValidationError("Cron field contains unsafe characters.")
        _validate_cron_field(field, minimum, maximum)
    return normalized


def _validate_cron_field(field: str, minimum: int, maximum: int) -> None:
    for list_part in field.split(","):
        base, separator, step = list_part.partition("/")
        if separator and (
            not step.isdigit() or int(step) < 1 or int(step) > maximum
        ):
            raise CronValidationError("Cron step is outside its range.")
        if base == "*":
            continue
        if "-" in base:
            start_text, end_text = base.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise CronValidationError("Cron range is invalid.")
            start, end = int(start_text), int(end_text)
            if start > end or start < minimum or end > maximum:
                raise CronValidationError("Cron range is outside its bounds.")
            continue
        if not base.isdigit() or not minimum <= int(base) <= maximum:
            raise CronValidationError("Cron value is outside its bounds.")


def report_schedule_not_found() -> Exception:
    return document_error(
        "The report schedule does not exist or is outside your scope.",
        code="REPORT_SCHEDULE_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Report schedule was not found.",
    )


class ReportScheduleService(DocumentServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.schedules = ReportScheduleRepository(session)
        self.filter_service = ReportFilterService(user)

    async def list(
        self,
        *,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> ReportScheduleListResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_VIEW)
        items, total = await self.schedules.list_page(
            department_ids=self.filter_service.query_scope(),
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return ReportScheduleListResponse(
            items=[report_schedule_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def create(
        self, payload: ReportScheduleCreateRequest
    ) -> ReportScheduleResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_CONFIGURE)
        filters = self.filter_service.validate(payload.filters)
        cron = self._resolve_cron(
            payload.schedule_type, payload.cron_expression
        )
        timezone = self._timezone(payload.timezone)
        now = utc_now()
        schedule = ReportSchedule(
            name=payload.name,
            report_type=payload.report_type,
            filters_json=filters.model_dump(mode="json", by_alias=True),
            formats_json=[item.value for item in payload.formats],
            schedule_type=payload.schedule_type,
            cron_expression=cron,
            timezone=timezone.key,
            is_active=True,
            scope_department_id=self.filter_service.scope_department_id(
                filters
            ),
            next_run_at=self._next_run(payload.schedule_type, now),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        await self.schedules.add(schedule)
        await self.audit(
            action=AuditAction.CREATE_REPORT_SCHEDULE,
            entity_type="ReportSchedule",
            entity_id=schedule.id,
            description="Advanced report schedule created.",
            new_values=self._audit_values(schedule),
        )
        await self.session.commit()
        await self.session.refresh(schedule)
        return report_schedule_response(schedule)

    async def update(
        self, schedule_id: UUID, payload: ReportScheduleUpdateRequest
    ) -> ReportScheduleResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_CONFIGURE)
        schedule = await self._get(schedule_id, for_update=True)
        old_values = self._audit_values(schedule)
        if payload.name is not None:
            schedule.name = payload.name.strip()
        if payload.report_type is not None:
            schedule.report_type = payload.report_type
        if payload.filters is not None:
            filters = self.filter_service.validate(payload.filters)
            schedule.filters_json = filters.model_dump(
                mode="json", by_alias=True
            )
            schedule.scope_department_id = (
                self.filter_service.scope_department_id(filters)
            )
        if payload.formats is not None:
            schedule.formats_json = [item.value for item in payload.formats]
        previous_schedule_type = schedule.schedule_type
        schedule_type = payload.schedule_type or previous_schedule_type
        if (
            payload.schedule_type is not None
            or payload.cron_expression is not None
        ):
            schedule.schedule_type = schedule_type
            cron_expression = payload.cron_expression
            if (
                cron_expression is None
                and payload.schedule_type is not None
            ):
                cron_expression = (
                    schedule.cron_expression
                    if (
                        schedule_type is ReportScheduleType.CUSTOM_CRON
                        and previous_schedule_type
                        is ReportScheduleType.CUSTOM_CRON
                    )
                    else None
                )
            schedule.cron_expression = self._resolve_cron(
                schedule_type,
                cron_expression,
            )
        if payload.timezone is not None:
            schedule.timezone = self._timezone(payload.timezone).key
        if payload.is_active is not None:
            schedule.is_active = payload.is_active
        schedule.updated_by = self.user.id
        schedule.next_run_at = (
            self._next_run(schedule.schedule_type, utc_now())
            if schedule.is_active
            else None
        )
        await self.audit(
            action=AuditAction.UPDATE_REPORT_SCHEDULE,
            entity_type="ReportSchedule",
            entity_id=schedule.id,
            description="Advanced report schedule updated.",
            old_values=old_values,
            new_values=self._audit_values(schedule),
        )
        await self.session.commit()
        await self.session.refresh(schedule)
        return report_schedule_response(schedule)

    async def run(self, schedule_id: UUID) -> ReportScheduleRunResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_CONFIGURE)
        schedule = await self._get(schedule_id, for_update=True)
        if not schedule.is_active:
            raise document_error(
                "Enable the report schedule before running it.",
                code="REPORT_SCHEDULE_DISABLED",
                status_code=HTTPStatus.CONFLICT,
            )
        filters = self.filter_service.validate(
            AdvancedReportFilters.model_validate(schedule.filters_json)
        )
        reporting = AdvancedReportingService(
            self.session, self.settings, self.user, self.metadata
        )
        snapshots = []
        for format_value in schedule.formats_json:
            output_format = ReportFileFormat(str(format_value))
            snapshot = await reporting._queue(
                report_type=schedule.report_type,
                report_name=schedule.name,
                filters=filters,
                output_format=output_format,
                metadata={
                    "includeCharts": True,
                    "includeDetailedTables": True,
                    "source": "SCHEDULE_MANUAL_RUN",
                    "scheduleId": str(schedule.id),
                },
                commit=False,
            )
            snapshots.append(snapshot)
        now = utc_now()
        schedule.last_run_at = now
        schedule.next_run_at = self._next_run(schedule.schedule_type, now)
        schedule.updated_by = self.user.id
        await self.audit(
            action=AuditAction.RUN_REPORT_SCHEDULE,
            entity_type="ReportSchedule",
            entity_id=schedule.id,
            description="Advanced report schedule executed manually.",
            new_values={
                "jobIds": [str(item.id) for item in snapshots],
                "formats": list(schedule.formats_json),
            },
        )
        await self.session.commit()
        for snapshot in snapshots:
            reporting._dispatch(snapshot.id)
        return ReportScheduleRunResponse(
            schedule_id=schedule.id,
            job_ids=[item.id for item in snapshots],
        )

    async def disable(
        self, schedule_id: UUID
    ) -> ReportScheduleResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_CONFIGURE)
        schedule = await self._get(schedule_id, for_update=True)
        schedule.is_active = False
        schedule.next_run_at = None
        schedule.updated_by = self.user.id
        await self.audit(
            action=AuditAction.DISABLE_REPORT_SCHEDULE,
            entity_type="ReportSchedule",
            entity_id=schedule.id,
            description="Advanced report schedule disabled.",
        )
        await self.session.commit()
        await self.session.refresh(schedule)
        return report_schedule_response(schedule)

    async def _get(
        self, schedule_id: UUID, *, for_update: bool
    ) -> ReportSchedule:
        schedule = await self.schedules.get_by_id(
            schedule_id,
            department_ids=self.filter_service.query_scope(),
            for_update=for_update,
        )
        if schedule is None:
            raise report_schedule_not_found()
        return schedule

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError(
                "You do not have permission to configure reports."
            )

    @staticmethod
    def _resolve_cron(
        schedule_type: ReportScheduleType,
        cron_expression: str | None,
    ) -> str:
        defaults = {
            ReportScheduleType.DAILY: "0 0 * * *",
            ReportScheduleType.WEEKLY: "0 0 * * 1",
            ReportScheduleType.MONTHLY: "0 0 1 * *",
        }
        if schedule_type is ReportScheduleType.CUSTOM_CRON:
            if not cron_expression or not cron_expression.strip():
                raise document_error(
                    "cronExpression is required for CUSTOM_CRON.",
                    field="cronExpression",
                    code="REPORT_CRON_REQUIRED",
                )
            try:
                return validate_cron_expression(cron_expression)
            except CronValidationError as exc:
                raise document_error(
                    str(exc),
                    field="cronExpression",
                    code="REPORT_CRON_INVALID",
                ) from exc
        value = cron_expression or defaults[schedule_type]
        try:
            return validate_cron_expression(value)
        except CronValidationError as exc:
            raise document_error(
                str(exc),
                field="cronExpression",
                code="REPORT_CRON_INVALID",
            ) from exc

    @staticmethod
    def _timezone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value.strip())
        except ZoneInfoNotFoundError as exc:
            raise document_error(
                "timezone must be a valid IANA timezone.",
                field="timezone",
                code="REPORT_TIMEZONE_INVALID",
            ) from exc

    @staticmethod
    def _next_run(
        schedule_type: ReportScheduleType, now: datetime
    ) -> datetime:
        if schedule_type is ReportScheduleType.DAILY:
            return now + timedelta(days=1)
        if schedule_type is ReportScheduleType.WEEKLY:
            return now + timedelta(days=7)
        if schedule_type is ReportScheduleType.MONTHLY:
            year = now.year + (1 if now.month == 12 else 0)
            month = 1 if now.month == 12 else now.month + 1
            day = min(now.day, monthrange(year, month)[1])
            return now.replace(year=year, month=month, day=day)
        # Configuration-only in Phase 9; no cron daemon is started.
        return now + timedelta(minutes=1)

    @staticmethod
    def _audit_values(schedule: ReportSchedule) -> dict[str, object]:
        return {
            "name": schedule.name,
            "reportType": schedule.report_type.value,
            "formats": list(schedule.formats_json),
            "scheduleType": schedule.schedule_type.value,
            "cronExpression": schedule.cron_expression,
            "timezone": schedule.timezone,
            "isActive": schedule.is_active,
        }


def report_schedule_response(
    item: ReportSchedule,
) -> ReportScheduleResponse:
    return ReportScheduleResponse(
        id=item.id,
        name=item.name,
        report_type=item.report_type,
        filters=item.filters_json,
        formats=[ReportFileFormat(value) for value in item.formats_json],
        schedule_type=item.schedule_type,
        cron_expression=item.cron_expression,
        timezone=item.timezone,
        is_active=item.is_active,
        last_run_at=item.last_run_at,
        next_run_at=item.next_run_at,
        created_by=item.created_by,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
