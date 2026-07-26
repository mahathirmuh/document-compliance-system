"""Celery task entry point for bounded Phase 8 compliance validation."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.compliance_enums import ComplianceJobStatus
from app.services.compliance.compliance_worker_service import (
    ComplianceWorkerService,
    TransientComplianceWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name="app.workers.compliance_tasks.process_compliance_job",
    max_retries=settings.compliance_max_retries,
    soft_time_limit=settings.compliance_task_soft_time_limit_seconds,
    time_limit=settings.compliance_task_time_limit_seconds,
)
def process_compliance_job(self, job_id: str) -> dict[str, str]:
    """Run one retained compliance job on the worker event loop."""

    service = ComplianceWorkerService(settings)
    retries = int(self.request.retries)
    try:
        status = run_async(
            service.process_job(
                UUID(job_id),
                worker_reference=str(self.request.id),
                attempt_number=retries + 1,
            )
        )
        return {"jobId": job_id, "status": status.value}
    except TransientComplianceWorkerError as exc:
        if retries >= settings.compliance_max_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="COMPLIANCE_WORKER_UNAVAILABLE",
                    error_message=(
                        "The compliance worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": job_id,
                "status": ComplianceJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc,
            countdown=min(60, 2 ** (retries + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="COMPLIANCE_TIMEOUT",
                error_message=(
                    "Compliance validation exceeded the configured time "
                    "limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": ComplianceJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": job_id,
            "status": ComplianceJobStatus.FAILED.value,
        }

