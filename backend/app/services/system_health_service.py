"""Cached dependency readiness and worker heartbeat aggregation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.worker_heartbeat_repository import (
    WorkerHeartbeatRepository,
)
from app.schemas.system_health import (
    DependencyHealthResponse,
    HealthComponentStatus,
    ReadinessResponse,
    SystemHealthResponse,
    WorkerHealthResponse,
)
from app.utils.datetime import utc_now

ProbeCallable = Callable[[], Awaitable[dict[str, object] | None]]


@dataclass(frozen=True, slots=True)
class DependencyProbe:
    name: str
    check: ProbeCallable
    mandatory: bool = True
    enabled: bool = True
    timeout_seconds: float = 3


class SystemHealthService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        probes: Sequence[DependencyProbe],
        expected_workers: Sequence[str],
        worker_stale_seconds: int = 120,
    ) -> None:
        self.heartbeats = WorkerHeartbeatRepository(session)
        self.probes = tuple(probes)
        self.expected_workers = tuple(dict.fromkeys(expected_workers))
        self.worker_stale_seconds = max(10, worker_stale_seconds)

    async def health(self) -> SystemHealthResponse:
        checked_at = utc_now()
        dependencies = await asyncio.gather(
            *(self._run_probe(probe, checked_at) for probe in self.probes)
        )
        workers = await self._worker_health(checked_at)
        status = self._overall_status(dependencies, workers)
        return SystemHealthResponse(
            status=status,
            checked_at=checked_at,
            dependencies=list(dependencies),
            workers=workers,
        )

    async def readiness(self) -> ReadinessResponse:
        health = await self.health()
        mandatory_names = {
            probe.name for probe in self.probes if probe.enabled and probe.mandatory
        }
        dependencies_ready = all(
            item.status == HealthComponentStatus.HEALTHY
            for item in health.dependencies
            if item.name in mandatory_names
        )
        workers_ready = all(
            item.status == HealthComponentStatus.HEALTHY for item in health.workers
        )
        ready = dependencies_ready and workers_ready
        return ReadinessResponse(
            ready=ready,
            status=(
                HealthComponentStatus.HEALTHY
                if ready
                else HealthComponentStatus.UNHEALTHY
            ),
        )

    async def _run_probe(
        self,
        probe: DependencyProbe,
        checked_at: datetime,
    ) -> DependencyHealthResponse:
        if not probe.enabled:
            return DependencyHealthResponse(
                name=probe.name,
                status=HealthComponentStatus.DISABLED,
                checked_at=checked_at,
                message="Integration is disabled.",
            )
        started = time.perf_counter()
        try:
            details = await asyncio.wait_for(
                probe.check(),
                timeout=probe.timeout_seconds,
            )
        except Exception:  # noqa: BLE001 - probe implementations are injected
            return DependencyHealthResponse(
                name=probe.name,
                status=HealthComponentStatus.UNHEALTHY,
                checked_at=checked_at,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="Dependency check failed.",
            )
        return DependencyHealthResponse(
            name=probe.name,
            status=HealthComponentStatus.HEALTHY,
            checked_at=checked_at,
            latency_ms=(time.perf_counter() - started) * 1000,
            details=details or {},
        )

    async def _worker_health(
        self,
        now: datetime,
    ) -> list[WorkerHealthResponse]:
        rows = {
            item.worker_name: item for item in await self.heartbeats.latest_by_worker()
        }
        result = []
        for worker_name in self.expected_workers:
            heartbeat = rows.get(worker_name)
            if heartbeat is None:
                result.append(
                    WorkerHealthResponse(
                        worker_name=worker_name,
                        queue_name=worker_name,
                        status=HealthComponentStatus.UNHEALTHY,
                        last_heartbeat_at=None,
                        age_seconds=None,
                    )
                )
                continue
            timestamp = heartbeat.last_heartbeat_at
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            age = max(0, (now - timestamp).total_seconds())
            result.append(
                WorkerHealthResponse(
                    worker_name=worker_name,
                    queue_name=heartbeat.queue_name,
                    status=(
                        HealthComponentStatus.HEALTHY
                        if age <= self.worker_stale_seconds
                        else HealthComponentStatus.UNHEALTHY
                    ),
                    last_heartbeat_at=timestamp,
                    age_seconds=age,
                )
            )
        return result

    @staticmethod
    def _overall_status(
        dependencies: Sequence[DependencyHealthResponse],
        workers: Sequence[WorkerHealthResponse],
    ) -> HealthComponentStatus:
        statuses = [item.status for item in (*dependencies, *workers)]
        if any(item == HealthComponentStatus.UNHEALTHY for item in statuses):
            return HealthComponentStatus.UNHEALTHY
        if any(item == HealthComponentStatus.DEGRADED for item in statuses):
            return HealthComponentStatus.DEGRADED
        return HealthComponentStatus.HEALTHY
