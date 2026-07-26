"""Worker composition for policy-driven retention and heartbeats."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import AsyncSessionFactory
from app.models.data_retention_policy import RetentionEntityType
from app.models.worker_heartbeat import WorkerHeartbeatState
from app.services.maintenance.retention_handlers import (
    create_default_retention_handlers,
)
from app.services.retention.contracts import RetentionEntityHandler
from app.services.retention.retention_service import RetentionService
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_factory import get_storage
from app.services.worker_heartbeat_service import WorkerHeartbeatService


class MaintenanceWorkerService:
    def __init__(
        self,
        *,
        handlers: Mapping[
            RetentionEntityType,
            RetentionEntityHandler,
        ]
        | None = None,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
        storage: BaseStorage | None = None,
    ) -> None:
        self.handlers = dict(handlers) if handlers is not None else None
        self.session_factory = session_factory
        self.storage = storage

    async def cleanup(
        self,
        *,
        entity_type: RetentionEntityType,
        dry_run: bool,
        batch_size: int,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            handlers = (
                self.handlers
                if self.handlers is not None
                else create_default_retention_handlers(
                    session,
                    storage=self.storage or get_storage(),
                )
            )
            if entity_type not in handlers:
                return {
                    "entityType": entity_type.value,
                    "status": "SKIPPED",
                    "reason": "RETENTION_JOB_FAILED",
                }
            result = await RetentionService(
                session,
                handlers=handlers,
            ).run(
                entity_type=entity_type,
                dry_run=dry_run,
                batch_size=batch_size,
            )
        return {
            **result.model_dump(mode="json", by_alias=True),
            "status": "COMPLETED",
        }

    async def heartbeat(
        self,
        *,
        worker_name: str,
        worker_instance: str,
        queue_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        async with self.session_factory() as session:
            heartbeat = await WorkerHeartbeatService(session).beat(
                worker_name=worker_name,
                worker_instance=worker_instance,
                queue_name=queue_name,
                state=WorkerHeartbeatState.ACTIVE,
                metadata=metadata,
            )
        return {
            "workerName": heartbeat.worker_name,
            "lastHeartbeatAt": heartbeat.last_heartbeat_at.isoformat(),
        }
