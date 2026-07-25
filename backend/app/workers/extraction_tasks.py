"""Celery tasks for durable document-content extraction jobs."""

from __future__ import annotations

import logging
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.extraction_job import ExtractionJobStatus
from app.services.automatic_pipeline_service import (
    AutomaticPipelineService,
)
from app.services.extraction.extraction_service import (
    ExtractionService,
    TransientExtractionWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.extraction_tasks.process_extraction_job",
    max_retries=settings.extraction_max_retries,
)
def process_extraction_job(self, job_id: str) -> dict[str, str]:
    """Run an async extraction safely inside one synchronous Celery task."""
    service = ExtractionService(settings)
    try:
        status = run_async(
            service.process_job(
                UUID(job_id),
                worker_reference=str(self.request.id),
                attempt_number=int(self.request.retries) + 1,
            )
        )
        try:
            run_async(
                AutomaticPipelineService(settings).after_extraction(
                    UUID(job_id),
                    status,
                )
            )
        except Exception:
            # An optional downstream feature must not rewrite an already
            # committed Phase 6 extraction outcome.
            logger.exception(
                "Automatic downstream orchestration failed after extraction "
                "job %s.",
                job_id,
            )
        return {"jobId": job_id, "status": status.value}
    except TransientExtractionWorkerError as exc:
        if int(self.request.retries) >= settings.extraction_max_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="EXTRACTION_WORKER_FAILED",
                    error_message=(
                        "The extraction worker remained unavailable after "
                        "retrying."
                    ),
                )
            )
            return {
                "jobId": job_id,
                "status": ExtractionJobStatus.FAILED.value,
            }
        raise self.retry(
            exc=exc,
            countdown=min(60, 2 ** (int(self.request.retries) + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="EXTRACTION_TIMEOUT",
                error_message=(
                    "Document extraction exceeded the configured time limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": ExtractionJobStatus.FAILED.value,
        }
    except (TypeError, ValueError):
        return {
            "jobId": job_id,
            "status": ExtractionJobStatus.FAILED.value,
        }
