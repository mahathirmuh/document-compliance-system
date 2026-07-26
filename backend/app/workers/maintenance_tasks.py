"""Policy-driven cleanup and cached worker-heartbeat Celery tasks."""

from __future__ import annotations

from typing import Any

from app.models.data_retention_policy import RetentionEntityType
from app.services.maintenance.maintenance_worker_service import (
    MaintenanceWorkerService,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

_service = MaintenanceWorkerService()


def configure_maintenance_worker_service(
    service: MaintenanceWorkerService,
) -> None:
    """Install entity-specific cleanup handlers during worker bootstrap."""

    global _service
    _service = service


def _cleanup(
    entity_type: RetentionEntityType,
    *,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    return run_async(
        _service.cleanup(
            entity_type=entity_type,
            dry_run=dry_run,
            batch_size=batch_size,
        )
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_temporary_files",
    queue="maintenance",
)
def cleanup_temporary_files(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.TEMP_UPLOAD,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_expired_report_snapshots",
    queue="maintenance",
)
def cleanup_expired_report_snapshots(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.REPORT_SNAPSHOT,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_old_notifications",
    queue="maintenance",
)
def cleanup_old_notifications(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.NOTIFICATION,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_webhook_events",
    queue="maintenance",
)
def cleanup_webhook_events(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.WEBHOOK_EVENT,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_job_results",
    queue="maintenance",
)
def cleanup_job_results(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.JOB_LOG,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_deleted_files",
    queue="maintenance",
)
def cleanup_deleted_files(
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    return _cleanup(
        RetentionEntityType.DELETED_FILE,
        dry_run=dry_run,
        batch_size=batch_size,
    )


@celery_app.task(
    name="app.workers.maintenance_tasks.update_worker_heartbeat",
    queue="maintenance",
)
def update_worker_heartbeat(
    worker_name: str,
    worker_instance: str,
    queue_name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    return run_async(
        _service.heartbeat(
            worker_name=worker_name,
            worker_instance=worker_instance,
            queue_name=queue_name,
            metadata=metadata,
        )
    )
