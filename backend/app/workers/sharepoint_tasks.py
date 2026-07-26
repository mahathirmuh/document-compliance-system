"""Celery tasks for SharePoint sync, delta webhooks, and renewal."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.database.session import AsyncSessionFactory
from app.models.sharepoint_enums import (
    SharePointSyncJobStatus,
    SyncItemStatus,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.services.maintenance.dead_letter_service import DeadLetterService
from app.services.sharepoint.sharepoint_worker_service import (
    SharePointWorkerService,
    TransientSharePointWorkerError,
)
from app.services.sharepoint.subscription_service import (
    GraphSubscriptionRenewalWorkerService,
)
from app.services.sharepoint.webhook_processing_service import (
    GraphWebhookProcessingService,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

settings = get_settings()


async def _record_dead_letter(
    *,
    task_name: str,
    entity_type: str,
    entity_id: UUID | None,
    attempts: int,
    error_code: str,
) -> None:
    async with AsyncSessionFactory() as session:
        sync = SharePointSyncRepository(session)
        if entity_type == "SharePointSyncJob" and entity_id is not None:
            job = await sync.get_job(entity_id, for_update=True)
            if job is not None:
                job.status = SharePointSyncJobStatus.DEAD_LETTER
                job.current_stage = "Dead letter"
                job.error_code = error_code
        elif entity_type == "SharePointSyncItem" and entity_id is not None:
            item = await sync.get_item(entity_id, for_update=True)
            if item is not None:
                item.status = SyncItemStatus.DEAD_LETTER
                item.error_code = error_code
        await DeadLetterService(session).record(
            task_name=task_name,
            entity_type=entity_type,
            entity_id=entity_id,
            attempts=attempts,
            maximum_attempts=int(settings.sharepoint_max_retries) + 1,
            arguments=(
                {"entityId": str(entity_id)}
                if entity_id is not None
                else {}
            ),
            error_code=error_code,
            safe_error=(
                "SharePoint background work exhausted its bounded retries."
            ),
        )


@celery_app.task(
    bind=True,
    name="app.workers.sharepoint_tasks.process_sharepoint_sync_job",
    max_retries=settings.sharepoint_max_retries,
    soft_time_limit=settings.sharepoint_task_soft_time_limit_seconds,
    time_limit=settings.sharepoint_task_time_limit_seconds,
)
def process_sharepoint_sync_job(
    self,
    job_id: str,
) -> dict[str, str]:
    service = SharePointWorkerService(settings)
    identifier = UUID(job_id)
    try:
        status = run_async(
            service.process_job(
                identifier,
                worker_reference=str(self.request.id),
            )
        )
        return {"jobId": job_id, "status": status.value}
    except TransientSharePointWorkerError as exc:
        retries = int(self.request.retries)
        if retries >= settings.sharepoint_max_retries:
            run_async(
                _record_dead_letter(
                    task_name=self.name,
                    entity_type="SharePointSyncJob",
                    entity_id=identifier,
                    attempts=retries + 1,
                    error_code="SHAREPOINT_RETRY_EXHAUSTED",
                )
            )
            return {
                "jobId": job_id,
                "status": SharePointSyncJobStatus.DEAD_LETTER.value,
            }
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (retries + 1)),
        )
    except SoftTimeLimitExceeded:
        run_async(
            service.fail_job(
                identifier,
                error_code="SHAREPOINT_SYNC_TIMEOUT",
                error_message=(
                    "SharePoint synchronization exceeded its time limit."
                ),
            )
        )
        return {
            "jobId": job_id,
            "status": SharePointSyncJobStatus.FAILED.value,
        }


@celery_app.task(
    bind=True,
    name="app.workers.sharepoint_tasks.process_sharepoint_sync_item",
    max_retries=settings.sharepoint_max_retries,
    soft_time_limit=settings.sharepoint_task_soft_time_limit_seconds,
    time_limit=settings.sharepoint_task_time_limit_seconds,
)
def process_sharepoint_sync_item(
    self,
    item_id: str,
) -> dict[str, str]:
    identifier = UUID(item_id)
    service = SharePointWorkerService(settings)
    try:
        status = run_async(service.process_item(identifier))
        return {"itemId": item_id, "status": status.value}
    except TransientSharePointWorkerError as exc:
        retries = int(self.request.retries)
        if retries >= settings.sharepoint_max_retries:
            run_async(
                _record_dead_letter(
                    task_name=self.name,
                    entity_type="SharePointSyncItem",
                    entity_id=identifier,
                    attempts=retries + 1,
                    error_code="SHAREPOINT_RETRY_EXHAUSTED",
                )
            )
            return {"itemId": item_id, "status": "DEAD_LETTER"}
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (retries + 1)),
        )


@celery_app.task(
    bind=True,
    name="app.workers.sharepoint_tasks.process_graph_webhook_event",
    max_retries=settings.sharepoint_max_retries,
    soft_time_limit=60,
    time_limit=90,
)
def process_graph_webhook_event(
    self,
    event_id: str,
) -> dict[str, str]:
    async def process() -> None:
        async with AsyncSessionFactory() as session:
            await GraphWebhookProcessingService(
                session,
                settings,
            ).process_event(UUID(event_id))

    try:
        run_async(process())
        return {"eventId": event_id, "status": "PROCESSED"}
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        retries = int(self.request.retries)
        if retries >= settings.sharepoint_max_retries:
            run_async(
                _record_dead_letter(
                    task_name=self.name,
                    entity_type="GraphWebhookEvent",
                    entity_id=UUID(event_id),
                    attempts=retries + 1,
                    error_code="GRAPH_WEBHOOK_RETRY_EXHAUSTED",
                )
            )
            return {"eventId": event_id, "status": "DEAD_LETTER"}
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (retries + 1)),
        )


@celery_app.task(
    bind=True,
    name="app.workers.sharepoint_tasks.renew_graph_subscriptions",
    max_retries=settings.sharepoint_max_retries,
    soft_time_limit=300,
    time_limit=360,
)
def renew_graph_subscriptions(self) -> dict[str, int]:
    try:
        return run_async(
            GraphSubscriptionRenewalWorkerService(
                settings
            ).renew_expiring()
        )
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        retries = int(self.request.retries)
        if retries >= settings.sharepoint_max_retries:
            run_async(
                _record_dead_letter(
                    task_name=self.name,
                    entity_type="GraphSubscriptionBatch",
                    entity_id=None,
                    attempts=retries + 1,
                    error_code="GRAPH_SUBSCRIPTION_RENEWAL_FAILED",
                )
            )
            return {"renewed": 0, "failed": 1}
        raise self.retry(
            exc=exc,
            countdown=min(1800, 30 * (2**retries)),
        )


@celery_app.task(
    bind=True,
    name="app.workers.sharepoint_tasks.reconcile_sharepoint_file",
    max_retries=settings.sharepoint_max_retries,
    soft_time_limit=settings.sharepoint_task_soft_time_limit_seconds,
    time_limit=settings.sharepoint_task_time_limit_seconds,
)
def reconcile_sharepoint_file(
    self,
    file_id: str,
) -> dict[str, str]:
    identifier = UUID(file_id)
    service = SharePointWorkerService(settings)
    try:
        status = run_async(
            service.reconcile_file(
                identifier,
                worker_reference=str(self.request.id),
            )
        )
        return {"fileId": file_id, "status": status.value}
    except TransientSharePointWorkerError as exc:
        retries = int(self.request.retries)
        if retries >= settings.sharepoint_max_retries:
            run_async(
                _record_dead_letter(
                    task_name=self.name,
                    entity_type="DocumentFile",
                    entity_id=identifier,
                    attempts=retries + 1,
                    error_code="SHAREPOINT_RETRY_EXHAUSTED",
                )
            )
            return {"fileId": file_id, "status": "DEAD_LETTER"}
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (retries + 1)),
        )
