"""Celery task entrypoint for bounded local scanned-PDF OCR."""

from __future__ import annotations

import logging
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.models.ocr_job import OCRJobStatus
from app.services.automatic_pipeline_service import (
    AutomaticPipelineService,
)
from app.services.ocr.ocr_service import (
    OCRService,
    TransientOCRWorkerError,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.ocr_tasks.process_ocr_job",
    autoretry_for=(),
    max_retries=int(getattr(settings, "ocr_max_retries", 1)),
    soft_time_limit=int(getattr(settings, "ocr_task_soft_time_limit_seconds", 3300)),
    time_limit=int(getattr(settings, "ocr_task_time_limit_seconds", 3600)),
)
def process_ocr_job(self, job_id: str) -> dict[str, str]:
    """Run one async OCR job on the worker child's persistent event loop."""
    service = OCRService(settings)
    request = self.request
    retries = int(request.retries)
    try:
        status = run_async(
            service.process_job(
                UUID(job_id),
                worker_reference=str(request.id),
                attempt_number=retries + 1,
            )
        )
        try:
            run_async(
                AutomaticPipelineService(settings).after_ocr(
                    UUID(job_id),
                    status,
                )
            )
        except Exception:
            # Preserve the committed OCR result if optional chaining fails.
            logger.exception(
                "Automatic language orchestration failed after OCR job %s.",
                job_id,
            )
        return {"jobId": job_id, "status": status.value}
    except TransientOCRWorkerError as exc:
        maximum_retries = int(getattr(settings, "ocr_max_retries", 1))
        if retries >= maximum_retries:
            run_async(
                service.fail_job(
                    UUID(job_id),
                    error_code="OCR_PROVIDER_UNAVAILABLE",
                    error_message=(
                        "The OCR worker remained unavailable after retrying."
                    ),
                )
            )
            return {"jobId": job_id, "status": OCRJobStatus.FAILED.value}
        raise self.retry(
            exc=exc,
            countdown=min(60, 2 ** (retries + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                UUID(job_id),
                error_code="OCR_TIMEOUT",
                error_message="OCR exceeded the configured time limit.",
            )
        )
        return {"jobId": job_id, "status": OCRJobStatus.FAILED.value}
    except (TypeError, ValueError):
        return {"jobId": job_id, "status": OCRJobStatus.FAILED.value}
