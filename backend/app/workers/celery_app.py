"""Celery application for private document-intelligence tasks."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "document_compliance",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=(
        "app.workers.extraction_tasks",
        "app.workers.ocr_tasks",
        "app.workers.language_detection_tasks",
        "app.workers.compliance_tasks",
    ),
)
celery_app.conf.update(
    accept_content=("json",),
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    result_expires=3600,
    result_serializer="json",
    task_acks_late=True,
    task_annotations={
        "app.workers.ocr_tasks.process_ocr_job": {
            "soft_time_limit": settings.ocr_task_soft_time_limit_seconds,
            "time_limit": settings.ocr_task_time_limit_seconds,
        },
        (
            "app.workers.language_detection_tasks."
            "process_language_detection_job"
        ): {
            "soft_time_limit": (
                settings.language_task_soft_time_limit_seconds
            ),
            "time_limit": settings.language_task_time_limit_seconds,
        },
        "app.workers.compliance_tasks.process_compliance_job": {
            "soft_time_limit": (
                settings.compliance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.compliance_task_time_limit_seconds,
        },
    },
    task_default_queue=settings.extraction_queue_name,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.workers.extraction_tasks.process_extraction_job": {
            "queue": settings.extraction_queue_name,
        },
        "app.workers.ocr_tasks.process_ocr_job": {
            "queue": settings.ocr_queue_name,
        },
        (
            "app.workers.language_detection_tasks."
            "process_language_detection_job"
        ): {
            "queue": settings.language_queue_name,
        },
        "app.workers.compliance_tasks.process_compliance_job": {
            "queue": settings.compliance_queue_name,
        },
    },
    task_serializer="json",
    task_soft_time_limit=settings.extraction_task_soft_time_limit_seconds,
    task_time_limit=settings.extraction_task_time_limit_seconds,
    task_track_started=True,
    timezone="UTC",
    worker_prefetch_multiplier=1,
)

__all__ = ["celery_app"]
