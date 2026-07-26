"""Persist throttled Celery worker heartbeats without using remote inspect."""

from __future__ import annotations

import logging
import time
from typing import Any

from celery.signals import heartbeat_sent, worker_shutting_down

from app.database.session import AsyncSessionFactory
from app.models.worker_heartbeat import WorkerHeartbeatState
from app.services.worker_heartbeat_service import WorkerHeartbeatService
from app.workers.runtime import run_async

logger = logging.getLogger(__name__)
_last_persisted_at = 0.0
_MINIMUM_PERSIST_INTERVAL_SECONDS = 30.0
_QUEUE_BY_WORKER = {
    "extraction": "extraction",
    "ocr": "ocr",
    "language": "language",
    "compliance": "compliance",
    "similarity": "similarity",
    "glossary": "glossary",
    "revision": "revision-comparison",
    "reporting": "reporting",
    "sharepoint": "sharepoint",
    "notifications": "notifications",
    "maintenance": "maintenance",
}


def _identity(sender: Any) -> tuple[str, str, str]:
    if isinstance(sender, str):
        # ``heartbeat_sent`` provides a Heart instance, while Celery's
        # ``worker_shutting_down`` signal provides the hostname directly.
        hostname = sender.strip() or "worker@unknown"
    else:
        eventer = getattr(sender, "eventer", None)
        hostname = str(
            getattr(eventer, "hostname", None)
            or getattr(sender, "hostname", None)
            or "worker@unknown"
        )
    prefix = hostname.split("@", maxsplit=1)[0].casefold()
    worker_name = prefix if prefix in _QUEUE_BY_WORKER else "unknown"
    return worker_name, hostname, _QUEUE_BY_WORKER.get(worker_name, prefix)


async def _persist(
    *,
    worker_name: str,
    worker_instance: str,
    queue_name: str,
    state: WorkerHeartbeatState,
) -> None:
    async with AsyncSessionFactory() as session:
        await WorkerHeartbeatService(session).beat(
            worker_name=worker_name,
            worker_instance=worker_instance,
            queue_name=queue_name,
            state=state,
            metadata={"source": "celery-heartbeat"},
        )


@heartbeat_sent.connect(weak=False)
def persist_worker_heartbeat(sender: Any = None, **_: object) -> None:
    """Write at most twice per minute even if Celery emits every two seconds."""

    global _last_persisted_at
    now = time.monotonic()
    if now - _last_persisted_at < _MINIMUM_PERSIST_INTERVAL_SECONDS:
        return
    _last_persisted_at = now
    worker_name, instance, queue = _identity(sender)
    try:
        run_async(
            _persist(
                worker_name=worker_name,
                worker_instance=instance,
                queue_name=queue,
                state=WorkerHeartbeatState.ACTIVE,
            )
        )
    except Exception:  # noqa: BLE001 - heartbeat failure cannot stop the worker
        logger.warning(
            "Worker heartbeat persistence failed.",
            extra={"event": "worker_heartbeat_failed"},
        )


@worker_shutting_down.connect(weak=False)
def persist_worker_shutdown(sender: Any = None, **_: object) -> None:
    worker_name, instance, queue = _identity(sender)
    try:
        run_async(
            _persist(
                worker_name=worker_name,
                worker_instance=instance,
                queue_name=queue,
                state=WorkerHeartbeatState.STOPPED,
            )
        )
    except Exception:  # noqa: BLE001 - shutdown must remain bounded
        logger.warning(
            "Worker shutdown heartbeat persistence failed.",
            extra={"event": "worker_heartbeat_shutdown_failed"},
        )
