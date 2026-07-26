"""Celery entry point for Phase 9 revision comparison."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.revision_comparison_job import RevisionComparisonJobStatus
from app.services.revision_comparison.revision_comparison_worker_service import (
    RevisionComparisonWorkerService,
    TransientRevisionComparisonWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name=(
        "app.workers.revision_comparison_tasks."
        "process_revision_comparison_job"
    ),
    max_retries=settings.revision_comparison_max_retries,
    soft_time_limit=settings.revision_comparison_task_soft_time_limit_seconds,
    time_limit=settings.revision_comparison_task_time_limit_seconds,
)
def process_revision_comparison_job(self, job_id: str) -> dict[str, str]:
    service = RevisionComparisonWorkerService(settings)
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
    except TransientRevisionComparisonWorkerError as exc:
        if retries >= settings.revision_comparison_max_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="REVISION_COMPARISON_WORKER_UNAVAILABLE",
                    error_message=(
                        "The comparison worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": job_id,
                "status": RevisionComparisonJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc, countdown=min(60, 2 ** (retries + 1))
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="REVISION_COMPARISON_TIMEOUT",
                error_message=(
                    "Revision comparison exceeded the configured time limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": RevisionComparisonJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": job_id,
            "status": RevisionComparisonJobStatus.FAILED.value,
        }
