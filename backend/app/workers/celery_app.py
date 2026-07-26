"""Celery application for private document-intelligence tasks."""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import get_settings
from app.workers import (
    task_correlation_signals as _task_correlation_signals,  # noqa: F401
)
from app.workers import (
    worker_heartbeat_signals as _worker_heartbeat_signals,  # noqa: F401
)

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
        "app.workers.similarity_tasks",
        "app.workers.glossary_tasks",
        "app.workers.revision_comparison_tasks",
        "app.workers.reporting_tasks",
        "app.workers.sharepoint_tasks",
        "app.workers.notification_tasks",
        "app.workers.maintenance_tasks",
    ),
)
celery_app.conf.update(
    accept_content=("json",),
    beat_schedule={
        "schedule-sharepoint-sync-jobs": {
            "task": (
                "app.workers.sharepoint_tasks."
                "schedule_sharepoint_sync_jobs"
            ),
            "schedule": max(
                60,
                settings.sharepoint_sync_interval_minutes * 60,
            ),
            "options": {"queue": settings.sharepoint_queue_name},
        },
        "renew-graph-subscriptions-hourly": {
            "task": (
                "app.workers.sharepoint_tasks."
                "renew_graph_subscriptions"
            ),
            "schedule": crontab(minute=15),
            "options": {"queue": settings.sharepoint_queue_name},
        },
        "expire-in-app-notifications": {
            "task": (
                "app.workers.notification_tasks."
                "expire_in_app_notifications"
            ),
            "schedule": crontab(minute="*/15"),
            "options": {"queue": settings.notification_queue_name},
        },
        "cleanup-temporary-files": {
            "task": "app.workers.maintenance_tasks.cleanup_temporary_files",
            "schedule": crontab(hour=1, minute=5),
            "options": {"queue": settings.maintenance_queue_name},
        },
        "cleanup-report-snapshots": {
            "task": (
                "app.workers.maintenance_tasks."
                "cleanup_expired_report_snapshots"
            ),
            "schedule": crontab(hour=1, minute=15),
            "options": {"queue": settings.maintenance_queue_name},
        },
        "cleanup-old-notifications": {
            "task": (
                "app.workers.maintenance_tasks.cleanup_old_notifications"
            ),
            "schedule": crontab(hour=1, minute=25),
            "options": {"queue": settings.maintenance_queue_name},
        },
        "cleanup-webhook-events": {
            "task": (
                "app.workers.maintenance_tasks.cleanup_webhook_events"
            ),
            "schedule": crontab(hour=1, minute=35),
            "options": {"queue": settings.maintenance_queue_name},
        },
        "cleanup-job-results": {
            "task": "app.workers.maintenance_tasks.cleanup_job_results",
            "schedule": crontab(hour=1, minute=45),
            "options": {"queue": settings.maintenance_queue_name},
        },
        "cleanup-deleted-files": {
            "task": "app.workers.maintenance_tasks.cleanup_deleted_files",
            "schedule": crontab(hour=2, minute=5),
            "options": {"queue": settings.maintenance_queue_name},
        },
    },
    broker_connection_retry_on_startup=(
        settings.celery_broker_connection_retry_on_startup
    ),
    enable_utc=True,
    result_expires=settings.celery_result_expires_seconds,
    result_serializer="json",
    task_acks_late=settings.celery_task_acks_late,
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
        "app.workers.similarity_tasks.process_similarity_job": {
            "soft_time_limit": (
                settings.similarity_task_soft_time_limit_seconds
            ),
            "time_limit": settings.similarity_task_time_limit_seconds,
        },
        "app.workers.glossary_tasks.process_glossary_validation_job": {
            "soft_time_limit": (
                settings.glossary_task_soft_time_limit_seconds
            ),
            "time_limit": settings.glossary_task_time_limit_seconds,
        },
        (
            "app.workers.revision_comparison_tasks."
            "process_revision_comparison_job"
        ): {
            "soft_time_limit": (
                settings.revision_comparison_task_soft_time_limit_seconds
            ),
            "time_limit": (
                settings.revision_comparison_task_time_limit_seconds
            ),
        },
        "app.workers.reporting_tasks.process_report_job": {
            "soft_time_limit": (
                settings.reporting_task_soft_time_limit_seconds
            ),
            "time_limit": settings.reporting_task_time_limit_seconds,
        },
        "app.workers.sharepoint_tasks.process_sharepoint_sync_job": {
            "soft_time_limit": (
                settings.sharepoint_task_soft_time_limit_seconds
            ),
            "time_limit": settings.sharepoint_task_time_limit_seconds,
        },
        "app.workers.sharepoint_tasks.schedule_sharepoint_sync_jobs": {
            "soft_time_limit": 120,
            "time_limit": 180,
        },
        "app.workers.sharepoint_tasks.process_sharepoint_sync_item": {
            "soft_time_limit": (
                settings.sharepoint_task_soft_time_limit_seconds
            ),
            "time_limit": settings.sharepoint_task_time_limit_seconds,
        },
        "app.workers.sharepoint_tasks.reconcile_sharepoint_file": {
            "soft_time_limit": (
                settings.sharepoint_task_soft_time_limit_seconds
            ),
            "time_limit": settings.sharepoint_task_time_limit_seconds,
        },
        "app.workers.notification_tasks.dispatch_notification": {
            "soft_time_limit": (
                settings.notification_task_soft_time_limit_seconds
            ),
            "time_limit": settings.notification_task_time_limit_seconds,
        },
        "app.workers.notification_tasks.retry_failed_notification": {
            "soft_time_limit": (
                settings.notification_task_soft_time_limit_seconds
            ),
            "time_limit": settings.notification_task_time_limit_seconds,
        },
        "app.workers.notification_tasks.process_notification_digest": {
            "soft_time_limit": (
                settings.notification_task_soft_time_limit_seconds
            ),
            "time_limit": settings.notification_task_time_limit_seconds,
        },
        "app.workers.notification_tasks.expire_in_app_notifications": {
            "soft_time_limit": (
                settings.notification_task_soft_time_limit_seconds
            ),
            "time_limit": settings.notification_task_time_limit_seconds,
        },
        "app.workers.maintenance_tasks.cleanup_temporary_files": {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
        (
            "app.workers.maintenance_tasks."
            "cleanup_expired_report_snapshots"
        ): {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
        "app.workers.maintenance_tasks.cleanup_old_notifications": {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
        "app.workers.maintenance_tasks.cleanup_webhook_events": {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
        "app.workers.maintenance_tasks.cleanup_job_results": {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
        "app.workers.maintenance_tasks.cleanup_deleted_files": {
            "soft_time_limit": (
                settings.maintenance_task_soft_time_limit_seconds
            ),
            "time_limit": settings.maintenance_task_time_limit_seconds,
        },
    },
    task_default_queue=settings.extraction_queue_name,
    task_create_missing_queues=False,
    task_queues=tuple(
        Queue(queue_name)
        for queue_name in (
            settings.extraction_queue_name,
            settings.ocr_queue_name,
            settings.language_queue_name,
            settings.compliance_queue_name,
            settings.similarity_queue_name,
            settings.glossary_queue_name,
            settings.revision_comparison_queue_name,
            settings.reporting_queue_name,
            settings.sharepoint_queue_name,
            settings.notification_queue_name,
            settings.maintenance_queue_name,
        )
    ),
    task_reject_on_worker_lost=(
        settings.celery_task_reject_on_worker_lost
    ),
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
        "app.workers.similarity_tasks.process_similarity_job": {
            "queue": settings.similarity_queue_name,
        },
        "app.workers.glossary_tasks.process_glossary_validation_job": {
            "queue": settings.glossary_queue_name,
        },
        (
            "app.workers.revision_comparison_tasks."
            "process_revision_comparison_job"
        ): {
            "queue": settings.revision_comparison_queue_name,
        },
        "app.workers.reporting_tasks.process_report_job": {
            "queue": settings.reporting_queue_name,
        },
        "app.workers.sharepoint_tasks.process_sharepoint_sync_job": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.sharepoint_tasks.schedule_sharepoint_sync_jobs": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.sharepoint_tasks.process_sharepoint_sync_item": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.sharepoint_tasks.process_graph_webhook_event": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.sharepoint_tasks.renew_graph_subscriptions": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.sharepoint_tasks.reconcile_sharepoint_file": {
            "queue": settings.sharepoint_queue_name,
        },
        "app.workers.notification_tasks.dispatch_notification": {
            "queue": settings.notification_queue_name,
        },
        "app.workers.notification_tasks.retry_failed_notification": {
            "queue": settings.notification_queue_name,
        },
        "app.workers.notification_tasks.process_notification_digest": {
            "queue": settings.notification_queue_name,
        },
        "app.workers.notification_tasks.expire_in_app_notifications": {
            "queue": settings.notification_queue_name,
        },
        "app.workers.maintenance_tasks.*": {
            "queue": settings.maintenance_queue_name,
        },
    },
    task_serializer="json",
    task_soft_time_limit=settings.extraction_task_soft_time_limit_seconds,
    task_time_limit=settings.extraction_task_time_limit_seconds,
    task_track_started=True,
    timezone="UTC",
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
)

__all__ = ["celery_app"]
