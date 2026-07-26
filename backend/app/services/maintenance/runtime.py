"""Bounded Celery recovery publisher for approved dead-letter task types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.core.config import Settings


class CeleryDeadLetterSender(Protocol):
    def send_task(
        self,
        name: str,
        *,
        args: list[str],
        queue: str,
        headers: dict[str, str],
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class DeadLetterTaskRoute:
    queue: str
    argument_key: str | None


class CeleryDeadLetterRetryPublisher:
    """Translate persisted safe identifiers for a fixed task allowlist."""

    def __init__(
        self,
        celery: CeleryDeadLetterSender,
        *,
        routes: Mapping[str, DeadLetterTaskRoute],
    ) -> None:
        if not routes:
            raise ValueError("At least one dead-letter task route is required.")
        self.celery = celery
        self.routes = dict(routes)

    async def publish(
        self,
        *,
        task_name: str,
        arguments: Mapping[str, Any],
        dead_letter_job_id: UUID,
    ) -> str | None:
        route = self.routes.get(task_name)
        if route is None:
            raise ValueError("Dead-letter task is not approved for retry.")
        positional_arguments: list[str] = []
        if route.argument_key is not None:
            raw_identifier = arguments.get(route.argument_key)
            try:
                identifier = UUID(str(raw_identifier))
            except (TypeError, ValueError) as exc:
                raise ValueError("Dead-letter task identifier is invalid.") from exc
            positional_arguments.append(str(identifier))
        task = self.celery.send_task(
            task_name,
            args=positional_arguments,
            queue=route.queue,
            headers={"dead_letter_job_id": str(dead_letter_job_id)},
        )
        task_id = getattr(task, "id", None)
        return str(task_id)[:1000] if task_id else None


def create_dead_letter_retry_publisher(
    settings: Settings,
    *,
    celery: CeleryDeadLetterSender,
) -> CeleryDeadLetterRetryPublisher:
    sharepoint = settings.sharepoint_queue_name
    notifications = settings.notification_queue_name
    return CeleryDeadLetterRetryPublisher(
        celery,
        routes={
            (
                "app.workers.sharepoint_tasks.process_sharepoint_sync_job"
            ): DeadLetterTaskRoute(
                queue=sharepoint,
                argument_key="entityId",
            ),
            (
                "app.workers.sharepoint_tasks.process_sharepoint_sync_item"
            ): DeadLetterTaskRoute(
                queue=sharepoint,
                argument_key="entityId",
            ),
            (
                "app.workers.sharepoint_tasks.process_graph_webhook_event"
            ): DeadLetterTaskRoute(
                queue=sharepoint,
                argument_key="entityId",
            ),
            (
                "app.workers.sharepoint_tasks.renew_graph_subscriptions"
            ): DeadLetterTaskRoute(
                queue=sharepoint,
                argument_key=None,
            ),
            (
                "app.workers.sharepoint_tasks.reconcile_sharepoint_file"
            ): DeadLetterTaskRoute(
                queue=sharepoint,
                argument_key="entityId",
            ),
            (
                "app.workers.notification_tasks.retry_failed_notification"
            ): DeadLetterTaskRoute(
                queue=notifications,
                argument_key="deliveryId",
            ),
        },
    )
