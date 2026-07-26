"""Bounded Celery entry points for the dedicated notification queue."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.services.notification.notification_worker_service import (
    NotificationWorkerService,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

_service = NotificationWorkerService()


def configure_notification_worker_service(
    service: NotificationWorkerService,
) -> None:
    """Configure external channel clients and retry rehydration at bootstrap."""

    global _service
    _service = service


@celery_app.task(
    name="app.workers.notification_tasks.dispatch_notification",
    queue="notifications",
)
def dispatch_notification(payload: Mapping[str, Any]) -> dict[str, str]:
    return run_async(_service.dispatch(payload))


@celery_app.task(
    name="app.workers.notification_tasks.retry_failed_notification",
    queue="notifications",
)
def retry_failed_notification(
    delivery_id: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    return run_async(_service.retry(UUID(delivery_id), payload))


@celery_app.task(
    name="app.workers.notification_tasks.process_notification_digest",
    queue="notifications",
)
def process_notification_digest(
    payloads: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return run_async(_service.digest(payloads))


@celery_app.task(
    name="app.workers.notification_tasks.expire_in_app_notifications",
    queue="notifications",
)
def expire_in_app_notifications(batch_size: int = 1000) -> dict[str, int]:
    return run_async(_service.expire_in_app(batch_size=batch_size))
