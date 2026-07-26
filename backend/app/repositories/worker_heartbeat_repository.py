"""Cached worker heartbeat queries; never calls Celery inspect."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.worker_heartbeat import WorkerHeartbeat


class WorkerHeartbeatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_instance(
        self,
        *,
        worker_name: str,
        worker_instance: str,
        for_update: bool = False,
    ) -> WorkerHeartbeat | None:
        statement = select(WorkerHeartbeat).where(
            WorkerHeartbeat.worker_name == worker_name,
            WorkerHeartbeat.worker_instance == worker_instance,
        )
        if for_update:
            statement = statement.with_for_update(of=WorkerHeartbeat)
        return await self.session.scalar(statement)

    async def add(self, heartbeat: WorkerHeartbeat) -> WorkerHeartbeat:
        self.session.add(heartbeat)
        await self.session.flush()
        return heartbeat

    async def latest_by_worker(self) -> list[WorkerHeartbeat]:
        statement = (
            select(WorkerHeartbeat)
            .distinct(WorkerHeartbeat.worker_name)
            .order_by(
                WorkerHeartbeat.worker_name.asc(),
                WorkerHeartbeat.last_heartbeat_at.desc(),
            )
        )
        if (
            self.session.bind is not None
            and self.session.bind.dialect.name != "postgresql"
        ):
            rows = list(
                await self.session.scalars(
                    select(WorkerHeartbeat).order_by(
                        WorkerHeartbeat.worker_name.asc(),
                        WorkerHeartbeat.last_heartbeat_at.desc(),
                    )
                )
            )
            latest: dict[str, WorkerHeartbeat] = {}
            for row in rows:
                latest.setdefault(row.worker_name, row)
            return list(latest.values())
        return list(await self.session.scalars(statement))

    async def stale_before(self, cutoff: datetime) -> list[WorkerHeartbeat]:
        statement = select(WorkerHeartbeat).where(
            WorkerHeartbeat.last_heartbeat_at < cutoff
        )
        return list(await self.session.scalars(statement))
