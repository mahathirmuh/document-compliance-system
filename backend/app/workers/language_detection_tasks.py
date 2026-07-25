"""Celery task entry point for Phase 7 language detection."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.language_detection_job import LanguageDetectionJobStatus
from app.services.language.language_detection_service import (
    LanguageDetectionService,
    TransientLanguageWorkerError,
)
from app.services.language.language_detector_factory import (
    get_worker_language_detector,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name=(
        "app.workers.language_detection_tasks."
        "process_language_detection_job"
    ),
    max_retries=settings.language_max_retries,
    soft_time_limit=settings.language_task_soft_time_limit_seconds,
    time_limit=settings.language_task_time_limit_seconds,
)
def process_language_detection_job(
    self,
    job_id: str,
) -> dict[str, str]:
    """Run async database orchestration on the persistent worker loop."""
    service = LanguageDetectionService(
        settings,
        detector=get_worker_language_detector(settings),
    )
    request = self.request
    retries = int(request.retries)
    worker_reference = str(request.id)
    try:
        status = run_async(
            service.process_job(
                UUID(job_id),
                worker_reference=worker_reference,
                attempt_number=retries + 1,
            )
        )
        return {"jobId": job_id, "status": status.value}
    except TransientLanguageWorkerError as exc:
        if retries >= settings.language_max_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="LANGUAGE_DETECTION_FAILED",
                    error_message=(
                        "The language worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": job_id,
                "status": LanguageDetectionJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc,
            countdown=min(60, 2 ** (retries + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="LANGUAGE_TIMEOUT",
                error_message=(
                    "Language detection exceeded the configured time limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": LanguageDetectionJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": job_id,
            "status": LanguageDetectionJobStatus.FAILED.value,
        }
