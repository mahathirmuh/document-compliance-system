"""Celery task entry point for local glossary validation."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.glossary_enums import GlossaryValidationStatus
from app.services.glossary.glossary_worker_service import (
    GlossaryWorkerService,
    TransientGlossaryWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


@celery_app.task(
    bind=True,
    name="app.workers.glossary_tasks.process_glossary_validation_job",
    max_retries=getattr(settings, "glossary_max_retries", 1),
    soft_time_limit=getattr(
        settings,
        "glossary_task_soft_time_limit_seconds",
        1800,
    ),
    time_limit=getattr(
        settings,
        "glossary_task_time_limit_seconds",
        1860,
    ),
)
def process_glossary_validation_job(
    self,
    run_id: str,
) -> dict[str, str]:
    """Run one retained glossary lifecycle on the worker event loop."""

    service = GlossaryWorkerService(settings)
    retries = int(self.request.retries)
    maximum_retries = int(getattr(settings, "glossary_max_retries", 1))
    try:
        status = run_async(
            service.process_job(
                UUID(run_id),
                worker_reference=str(self.request.id),
                attempt_number=retries + 1,
            )
        )
        return {"jobId": run_id, "runId": run_id, "status": status.value}
    except TransientGlossaryWorkerError as exc:
        if retries >= maximum_retries:
            run_async(
                service.fail_job(
                    UUID(run_id),
                    error_code="GLOSSARY_WORKER_UNAVAILABLE",
                    error_message=(
                        "Glossary worker remained unavailable after retrying."
                    ),
                )
            )
            return {
                "jobId": run_id,
                "runId": run_id,
                "status": GlossaryValidationStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc,
            countdown=min(60, 2 ** (retries + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(run_id),
                error_code="GLOSSARY_TIMEOUT",
                error_message=(
                    "Glossary validation exceeded its configured time limit."
                ),
            )
        )
        return {
            "jobId": run_id,
            "runId": run_id,
            "status": GlossaryValidationStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": run_id,
            "runId": run_id,
            "status": GlossaryValidationStatus.FAILED.value,
        }
