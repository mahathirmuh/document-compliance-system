"""Persist lightweight worker presence for cached health checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.worker_heartbeat import (
    WorkerHeartbeat,
    WorkerHeartbeatState,
)
from app.repositories.worker_heartbeat_repository import (
    WorkerHeartbeatRepository,
)
from app.utils.datetime import utc_now


class WorkerHeartbeatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkerHeartbeatRepository(session)

    async def beat(
        self,
        *,
        worker_name: str,
        worker_instance: str,
        queue_name: str,
        state: WorkerHeartbeatState = WorkerHeartbeatState.ACTIVE,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> WorkerHeartbeat:
        timestamp = now or utc_now()
        heartbeat = await self.repository.get_instance(
            worker_name=worker_name,
            worker_instance=worker_instance,
            for_update=True,
        )
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(
                worker_name=worker_name[:100],
                worker_instance=worker_instance[:255],
                queue_name=queue_name[:100],
                state=state,
                last_heartbeat_at=timestamp,
                started_at=timestamp,
                metadata_json=metadata or {},
            )
            await self.repository.add(heartbeat)
        else:
            heartbeat.queue_name = queue_name[:100]
            heartbeat.state = state
            heartbeat.last_heartbeat_at = timestamp
            heartbeat.metadata_json = metadata or {}
        await self.session.commit()
        await self.session.refresh(heartbeat)
        return heartbeat
