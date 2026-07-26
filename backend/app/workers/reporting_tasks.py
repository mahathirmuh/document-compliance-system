"""Celery entry point for Phase 9 advanced reports."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.report_snapshot import ReportJobStatus
from app.services.reporting.reporting_worker_service import (
    ReportingWorkerService,
    TransientReportingWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name="app.workers.reporting_tasks.process_report_job",
    max_retries=settings.reporting_max_retries,
    soft_time_limit=settings.reporting_task_soft_time_limit_seconds,
    time_limit=settings.reporting_task_time_limit_seconds,
)
def process_report_job(self, snapshot_id: str) -> dict[str, str]:
    service = ReportingWorkerService(settings)
    retries = int(self.request.retries)
    try:
        status = run_async(
            service.process_snapshot(
                UUID(snapshot_id), worker_reference=str(self.request.id)
            )
        )
        return {"jobId": snapshot_id, "status": status.value}
    except TransientReportingWorkerError as exc:
        if retries >= settings.reporting_max_retries:
            run_async(
                service.fail_snapshot(
                    UUID(snapshot_id),
                    error_code="REPORTING_WORKER_UNAVAILABLE",
                    error_message=(
                        "The reporting worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": snapshot_id,
                "status": ReportJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc, countdown=min(60, 2 ** (retries + 1))
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_snapshot(
                UUID(snapshot_id),
                error_code="REPORT_GENERATION_TIMEOUT",
                error_message=(
                    "Report generation exceeded the configured time limit."
                ),
            )
        )
        return {
            "jobId": snapshot_id,
            "status": ReportJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": snapshot_id,
            "status": ReportJobStatus.FAILED.value,
        }
