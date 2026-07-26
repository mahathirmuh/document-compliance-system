"""Celery entry point for bounded local similarity analysis."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.similarity_enums import SimilarityJobStatus
from app.services.similarity.similarity_worker_service import (
    SimilarityWorkerService,
    TransientSimilarityWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name="app.workers.similarity_tasks.process_similarity_job",
    max_retries=int(getattr(settings, "similarity_max_retries", 1)),
    soft_time_limit=int(
        getattr(
            settings,
            "similarity_task_soft_time_limit_seconds",
            3300,
        )
    ),
    time_limit=int(
        getattr(settings, "similarity_task_time_limit_seconds", 3600)
    ),
)
def process_similarity_job(self, job_id: str) -> dict[str, str]:
    service = SimilarityWorkerService(settings)
    retries = int(self.request.retries)
    maximum_retries = int(
        getattr(settings, "similarity_max_retries", 1)
    )
    try:
        status = run_async(
            service.process_job(
                UUID(job_id),
                worker_reference=str(self.request.id),
                attempt_number=retries + 1,
            )
        )
        return {"jobId": job_id, "status": status.value}
    except TransientSimilarityWorkerError as exc:
        if retries >= maximum_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="SIMILARITY_WORKER_UNAVAILABLE",
                    error_message=(
                        "The similarity worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": job_id,
                "status": SimilarityJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc, countdown=min(60, 2 ** (retries + 1))
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="SIMILARITY_TIMEOUT",
                error_message=(
                    "Similarity analysis exceeded the configured time limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": SimilarityJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": job_id,
            "status": SimilarityJobStatus.FAILED.value,
        }
