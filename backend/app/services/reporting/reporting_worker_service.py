"""Celery-side dataset, export, and private storage orchestration."""

from __future__ import annotations

import hashlib
import io
import json
import logging
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.models.report_snapshot import (
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.report_snapshot_repository import (
    ReportSnapshotRepository,
)
from app.schemas.advanced_reporting import AdvancedReportFilters
from app.services.reporting.report_dataset_service import ReportDatasetService
from app.services.reporting.report_export_service import ReportExportService
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_factory import StorageFactory
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class TransientReportingWorkerError(RuntimeError):
    """Infrastructure failure eligible for bounded retry."""


class ReportingWorkerService:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
        storage: BaseStorage | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.storage = storage or StorageFactory.get_storage(settings)

    async def process_snapshot(
        self,
        snapshot_id: UUID,
        *,
        worker_reference: str,
    ) -> ReportJobStatus:
        storage_key: str | None = None
        try:
            async with self.session_factory() as session:
                snapshots = ReportSnapshotRepository(session)
                snapshot = await snapshots.get_by_id(
                    snapshot_id, department_ids=None, for_update=True
                )
                if snapshot is None:
                    return ReportJobStatus.FAILED
                if snapshot.status is ReportSnapshotStatus.DELETED:
                    if snapshot.job_status not in {
                        ReportJobStatus.COMPLETED,
                        ReportJobStatus.FAILED,
                        ReportJobStatus.CANCELLED,
                    }:
                        snapshot.job_status = ReportJobStatus.CANCELLED
                        snapshot.current_stage = "Deleted"
                        await session.commit()
                    return snapshot.job_status
                if snapshot.job_status in {
                    ReportJobStatus.COMPLETED,
                    ReportJobStatus.FAILED,
                    ReportJobStatus.CANCELLED,
                }:
                    return snapshot.job_status
                snapshot.started_at = snapshot.started_at or utc_now()
                snapshot.job_status = ReportJobStatus.BUILDING_DATASET
                snapshot.status = ReportSnapshotStatus.GENERATING
                snapshot.progress = 10
                snapshot.current_stage = "Building scoped report dataset"
                snapshot.metadata_json = {
                    **snapshot.metadata_json,
                    "workerReference": worker_reference,
                }
                await session.commit()

                filters = AdvancedReportFilters.model_validate(
                    snapshot.filters_json
                )
                dataset = await ReportDatasetService(
                    session,
                    maximum_rows=self.settings.report_export_max_rows,
                    maximum_chart_categories=(
                        self.settings.report_chart_max_categories
                    ),
                ).build(snapshot.report_type, filters)
                if await self._deleted_while_running(session, snapshot):
                    return snapshot.job_status
                dataset = replace(
                    dataset,
                    data_series=(
                        dataset.data_series
                        if bool(
                            snapshot.metadata_json.get(
                                "includeCharts", True
                            )
                        )
                        else []
                    ),
                    tables=(
                        dataset.tables
                        if bool(
                            snapshot.metadata_json.get(
                                "includeDetailedTables", True
                            )
                        )
                        else {}
                    ),
                )
                snapshot.job_status = ReportJobStatus.GENERATING_CHARTS
                snapshot.progress = 45
                snapshot.current_stage = "Preparing bounded report views"
                await session.commit()

                snapshot.job_status = ReportJobStatus.CREATING_FILE
                snapshot.progress = 65
                snapshot.current_stage = "Creating private report artifact"
                await session.commit()
                exporter = ReportExportService(
                    xlsx_maximum_rows=(
                        self.settings.report_xlsx_max_rows_per_sheet
                    ),
                    pdf_maximum_rows=(
                        self.settings.report_pdf_max_table_rows
                    ),
                    text_maximum_characters=(
                        self.settings.report_text_snippet_max_characters
                    ),
                )
                content = exporter.build(
                    dataset,
                    report_name=snapshot.report_name,
                    filters=filters,
                    output_format=snapshot.file_format,
                )
                if await self._deleted_while_running(session, snapshot):
                    return snapshot.job_status
                canonical_dataset = json.dumps(
                    asdict(dataset),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
                snapshot.dataset_hash = hashlib.sha256(
                    canonical_dataset
                ).hexdigest()

                snapshot.job_status = ReportJobStatus.STORING_FILE
                snapshot.progress = 85
                snapshot.current_stage = "Storing report in private storage"
                await session.commit()
                locked_snapshot = await snapshots.get_by_id(
                    snapshot_id,
                    department_ids=None,
                    for_update=True,
                )
                if locked_snapshot is None:
                    return ReportJobStatus.FAILED
                snapshot = locked_snapshot
                if await self._deleted_while_running(session, snapshot):
                    return snapshot.job_status
                now = datetime.now(UTC)
                storage_key = (
                    f"reports/snapshots/{now.year:04d}/"
                    f"{now.month:02d}/{snapshot.id}."
                    f"{snapshot.file_format.value}"
                )
                result = await self.storage.save(
                    io.BytesIO(content), storage_key
                )
                snapshot.storage_key = result["storage_key"]
                snapshot.file_size = result["size"]
                snapshot.job_status = ReportJobStatus.COMPLETED
                snapshot.status = ReportSnapshotStatus.AVAILABLE
                snapshot.progress = 100
                snapshot.current_stage = "Completed"
                snapshot.generated_at = utc_now()
                snapshot.metadata_json = {
                    **snapshot.metadata_json,
                    "warningCount": len(dataset.warnings),
                    "tableCount": len(dataset.tables),
                    "privacy": {
                        "fullTextIncluded": False,
                        "storagePathExposed": False,
                        "ocrImagesIncluded": False,
                    },
                }
                await AuditLogRepository(session).create(
                    action=AuditAction.GENERATE_ADVANCED_REPORT,
                    description="Advanced report generation completed.",
                    user_id=snapshot.generated_by,
                    entity_type="ReportSnapshot",
                    entity_id=snapshot.id,
                    new_values={
                        "status": snapshot.status.value,
                        "format": snapshot.file_format.value,
                        "fileSize": snapshot.file_size,
                    },
                )
                await session.commit()
                return snapshot.job_status
        except SQLAlchemyError as exc:
            if storage_key and await self.storage.exists(storage_key):
                await self.storage.delete(storage_key)
            raise TransientReportingWorkerError(
                "The reporting database operation failed."
            ) from exc
        except Exception:
            logger.exception(
                "Unexpected report snapshot generation failure",
                extra={"snapshot_id": str(snapshot_id)},
            )
            if storage_key and await self.storage.exists(storage_key):
                await self.storage.delete(storage_key)
            await self.fail_snapshot(
                snapshot_id,
                error_code="REPORT_GENERATION_FAILED",
                error_message=(
                    "Report generation failed unexpectedly. Review worker "
                    "logs for diagnostic details."
                ),
            )
            return ReportJobStatus.FAILED

    @staticmethod
    async def _deleted_while_running(
        session: AsyncSession,
        snapshot: ReportSnapshot,
    ) -> bool:
        """Refresh lifecycle state and stop a soft-deleted active job."""

        await session.refresh(snapshot)
        if snapshot.status is not ReportSnapshotStatus.DELETED:
            return False
        if snapshot.job_status not in {
            ReportJobStatus.COMPLETED,
            ReportJobStatus.FAILED,
            ReportJobStatus.CANCELLED,
        }:
            snapshot.job_status = ReportJobStatus.CANCELLED
            snapshot.current_stage = "Deleted"
            await session.commit()
        return True

    async def fail_snapshot(
        self, snapshot_id: UUID, *, error_code: str, error_message: str
    ) -> None:
        async with self.session_factory() as session:
            snapshot = await ReportSnapshotRepository(session).get_by_id(
                snapshot_id, department_ids=None, for_update=True
            )
            if snapshot is None or snapshot.job_status in {
                ReportJobStatus.COMPLETED,
                ReportJobStatus.CANCELLED,
            }:
                return
            snapshot.job_status = ReportJobStatus.FAILED
            snapshot.status = ReportSnapshotStatus.FAILED
            snapshot.progress = min(snapshot.progress, 99)
            snapshot.current_stage = "Failed"
            snapshot.error_code = error_code[:100]
            snapshot.error_message = error_message[:2000]
            await AuditLogRepository(session).create(
                action=AuditAction.GENERATE_ADVANCED_REPORT,
                description="Advanced report generation failed.",
                user_id=snapshot.generated_by,
                entity_type="ReportSnapshot",
                entity_id=snapshot.id,
                new_values={"status": "FAILED", "errorCode": error_code},
            )
            await session.commit()
