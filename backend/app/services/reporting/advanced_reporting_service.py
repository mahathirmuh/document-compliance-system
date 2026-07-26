"""Queue and securely expose private Phase 9 report snapshots."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.models.user import User
from app.repositories.report_snapshot_repository import (
    ReportSnapshotRepository,
)
from app.schemas.advanced_reporting import (
    AdvancedReportFilters,
    AdvancedReportGenerateRequest,
    AdvancedReportJobListResponse,
    AdvancedReportJobResponse,
    ReportSnapshotDeleteResponse,
    ReportSnapshotListResponse,
    ReportSnapshotResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import DocumentServiceBase, document_error
from app.services.reporting.report_filter_service import ReportFilterService
from app.services.storage.base_storage import BaseStorage
from app.services.storage.file_stream_service import stream_storage
from app.services.storage.storage_factory import StorageFactory
from app.utils.datetime import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class ReportDownload:
    body: AsyncIterator[bytes]
    filename: str
    media_type: str
    file_size: int


def report_snapshot_not_found() -> Exception:
    return document_error(
        "The report snapshot does not exist or is outside your scope.",
        code="REPORT_SNAPSHOT_NOT_FOUND",
        status_code=HTTPStatus.NOT_FOUND,
        title="Report snapshot was not found.",
    )


class AdvancedReportingService(DocumentServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
        *,
        storage: BaseStorage | None = None,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.snapshots = ReportSnapshotRepository(session)
        self.filters = ReportFilterService(user)
        self.storage = storage or StorageFactory.get_storage(settings)

    async def generate(
        self, payload: AdvancedReportGenerateRequest
    ) -> AdvancedReportJobResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_EXPORT)
        filters = self.filters.validate(payload.filters)
        snapshot = await self._queue(
            report_type=payload.report_type,
            report_name=payload.report_name,
            filters=filters,
            output_format=payload.output_format,
            metadata={
                "includeCharts": payload.include_charts,
                "includeDetailedTables": payload.include_detailed_tables,
                "source": "MANUAL",
            },
            commit=True,
        )
        self._dispatch(snapshot.id)
        return report_job_response(snapshot)

    async def _queue(
        self,
        *,
        report_type: AdvancedReportType,
        report_name: str,
        filters: AdvancedReportFilters,
        output_format: ReportFileFormat,
        metadata: dict[str, object],
        commit: bool,
    ) -> ReportSnapshot:
        now = utc_now()
        snapshot = ReportSnapshot(
            report_type=report_type,
            report_name=report_name.strip(),
            filters_json=filters.model_dump(mode="json", by_alias=True),
            status=ReportSnapshotStatus.GENERATING,
            job_status=ReportJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            generated_by=self.user.id,
            scope_department_id=self.filters.scope_department_id(filters),
            requested_at=now,
            file_format=output_format,
            expires_at=now
            + timedelta(days=self.settings.report_snapshot_retention_days),
            metadata_json=metadata,
        )
        await self.snapshots.add(snapshot)
        await self.audit(
            action=AuditAction.GENERATE_ADVANCED_REPORT,
            entity_type="ReportSnapshot",
            entity_id=snapshot.id,
            description="Advanced report generation queued.",
            new_values={
                "reportType": report_type.value,
                "format": output_format.value,
                "filters": filters.model_dump(mode="json", by_alias=True),
            },
        )
        if commit:
            await self.session.commit()
        return snapshot

    async def list_jobs(
        self,
        *,
        report_types: list[AdvancedReportType] | None,
        statuses: list[ReportJobStatus] | None,
        page: int,
        page_size: int,
    ) -> AdvancedReportJobListResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_VIEW)
        items, total = await self.snapshots.list_page(
            department_ids=self.filters.query_scope(),
            report_types=report_types,
            statuses=None,
            job_statuses=statuses,
            page=page,
            page_size=page_size,
        )
        return AdvancedReportJobListResponse(
            items=[report_job_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def get_job(
        self, snapshot_id: UUID
    ) -> AdvancedReportJobResponse:
        item = await self._snapshot(
            snapshot_id, Permission.ADVANCED_REPORTS_VIEW
        )
        return report_job_response(item)

    async def list_snapshots(
        self,
        *,
        report_types: list[AdvancedReportType] | None,
        statuses: list[ReportSnapshotStatus] | None,
        file_formats: list[ReportFileFormat] | None,
        date_from: date | None,
        date_to: date | None,
        page: int,
        page_size: int,
    ) -> ReportSnapshotListResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_VIEW)
        if (
            date_from is not None
            and date_to is not None
            and date_to < date_from
        ):
            raise document_error(
                "dateTo must be on or after dateFrom.",
                field="dateTo",
                code="REPORT_SNAPSHOT_DATE_RANGE_INVALID",
            )
        items, total = await self.snapshots.list_page(
            department_ids=self.filters.query_scope(),
            report_types=report_types,
            statuses=statuses,
            job_statuses=None,
            file_formats=file_formats,
            generated_from=(
                datetime.combine(date_from, time.min, tzinfo=UTC)
                if date_from is not None
                else None
            ),
            generated_to=(
                datetime.combine(
                    date_to + timedelta(days=1),
                    time.min,
                    tzinfo=UTC,
                )
                if date_to is not None
                else None
            ),
            page=page,
            page_size=page_size,
        )
        return ReportSnapshotListResponse(
            items=[report_snapshot_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def get_snapshot(
        self, snapshot_id: UUID
    ) -> ReportSnapshotResponse:
        item = await self._snapshot(
            snapshot_id, Permission.ADVANCED_REPORTS_VIEW
        )
        return report_snapshot_response(item)

    async def prepare_download(self, snapshot_id: UUID) -> ReportDownload:
        item = await self._snapshot(
            snapshot_id, Permission.ADVANCED_REPORTS_EXPORT
        )
        now = utc_now()
        if (
            item.expires_at is not None
            and ensure_utc(item.expires_at) <= now
        ):
            item.status = ReportSnapshotStatus.EXPIRED
            await self.session.commit()
            raise document_error(
                "The report snapshot has expired.",
                code="REPORT_SNAPSHOT_EXPIRED",
                status_code=HTTPStatus.GONE,
                title="Report snapshot is no longer available.",
            )
        if (
            item.status is not ReportSnapshotStatus.AVAILABLE
            or item.job_status is not ReportJobStatus.COMPLETED
            or item.storage_key is None
            or item.file_size is None
        ):
            raise document_error(
                "The report snapshot is not available for download.",
                code="REPORT_SNAPSHOT_NOT_AVAILABLE",
                status_code=HTTPStatus.CONFLICT,
                title="Report snapshot is not ready.",
            )
        if not await self.storage.exists(item.storage_key):
            raise document_error(
                "The report artifact is no longer available.",
                code="REPORT_SNAPSHOT_STORAGE_MISSING",
                status_code=HTTPStatus.GONE,
                title="Report snapshot is unavailable.",
            )
        await self.audit(
            action=AuditAction.DOWNLOAD_ADVANCED_REPORT,
            entity_type="ReportSnapshot",
            entity_id=item.id,
            description="Advanced report snapshot downloaded.",
            new_values={"format": item.file_format.value},
        )
        await self.session.commit()
        filename = self._filename(item)
        return ReportDownload(
            body=stream_storage(
                self.storage,
                item.storage_key,
                chunk_size=self.settings.file_download_chunk_size_kb * 1024,
            ),
            filename=filename,
            media_type=self._media_type(item.file_format),
            file_size=item.file_size,
        )

    async def delete(
        self, snapshot_id: UUID
    ) -> ReportSnapshotDeleteResponse:
        self._ensure_permission(Permission.ADVANCED_REPORTS_EXPORT)
        item = await self.snapshots.get_by_id(
            snapshot_id,
            department_ids=self.filters.query_scope(),
            for_update=True,
        )
        if item is None:
            raise report_snapshot_not_found()
        if item.status is ReportSnapshotStatus.DELETED:
            if item.job_status not in {
                ReportJobStatus.COMPLETED,
                ReportJobStatus.FAILED,
                ReportJobStatus.CANCELLED,
            }:
                item.job_status = ReportJobStatus.CANCELLED
                item.current_stage = "Deleted"
                await self.session.commit()
            return ReportSnapshotDeleteResponse(
                snapshot_id=item.id, status=item.status
            )
        if item.storage_key and await self.storage.exists(item.storage_key):
            destination = (
                f"reports/deleted/{item.id}.{item.file_format.value}"
            )
            if await self.storage.exists(destination):
                await self.storage.delete(destination)
            await self.storage.move(item.storage_key, destination)
            item.metadata_json = {
                **item.metadata_json,
                "deletedStorageRetained": True,
            }
        item.storage_key = None
        item.status = ReportSnapshotStatus.DELETED
        if item.job_status not in {
            ReportJobStatus.COMPLETED,
            ReportJobStatus.FAILED,
            ReportJobStatus.CANCELLED,
        }:
            item.job_status = ReportJobStatus.CANCELLED
            item.current_stage = "Deleted"
        await self.audit(
            action=AuditAction.DELETE_REPORT_SNAPSHOT,
            entity_type="ReportSnapshot",
            entity_id=item.id,
            description="Advanced report snapshot soft deleted.",
        )
        await self.session.commit()
        return ReportSnapshotDeleteResponse(
            snapshot_id=item.id, status=item.status
        )

    async def _snapshot(
        self, snapshot_id: UUID, permission: Permission
    ) -> ReportSnapshot:
        self._ensure_permission(permission)
        item = await self.snapshots.get_by_id(
            snapshot_id,
            department_ids=self.filters.query_scope(),
        )
        if item is None:
            raise report_snapshot_not_found()
        return item

    def _dispatch(self, snapshot_id: UUID) -> None:
        from app.workers.celery_app import celery_app

        celery_app.send_task(
            "app.workers.reporting_tasks.process_report_job",
            args=[str(snapshot_id)],
            queue=self.settings.reporting_queue_name,
        )

    def _ensure_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise AuthorizationError(
                "You do not have permission to perform this report action."
            )

    @staticmethod
    def _filename(item: ReportSnapshot) -> str:
        safe = "".join(
            character
            if (
                character.isascii()
                and (
                    character.isalnum()
                    or character in {"-", "_"}
                )
            )
            else "-"
            for character in item.report_name
        ).strip("-")[:100] or "advanced-report"
        return f"{safe}-{item.id}.{item.file_format.value}"

    @staticmethod
    def _media_type(output_format: ReportFileFormat) -> str:
        return {
            ReportFileFormat.JSON: "application/json",
            ReportFileFormat.XLSX: (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            ReportFileFormat.PDF: "application/pdf",
        }[output_format]


def report_job_response(item: ReportSnapshot) -> AdvancedReportJobResponse:
    return AdvancedReportJobResponse(
        id=item.id,
        report_type=item.report_type,
        report_name=item.report_name,
        output_format=item.file_format,
        status=item.job_status,
        snapshot_status=item.status,
        progress=item.progress,
        current_stage=item.current_stage,
        requested_at=item.requested_at,
        started_at=item.started_at,
        completed_at=item.generated_at,
        error_code=item.error_code,
        error_message=item.error_message,
    )


def report_snapshot_response(
    item: ReportSnapshot,
) -> ReportSnapshotResponse:
    return ReportSnapshotResponse(
        id=item.id,
        report_type=item.report_type,
        report_name=item.report_name,
        filters=item.filters_json,
        dataset_hash=item.dataset_hash,
        status=item.status,
        job_status=item.job_status,
        generated_by=item.generated_by,
        generated_at=item.generated_at,
        file_format=item.file_format,
        file_size=item.file_size,
        expires_at=item.expires_at,
        metadata=item.metadata_json,
        created_at=item.created_at,
    )
