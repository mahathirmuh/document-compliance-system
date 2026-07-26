"""Dependency, worker, and readiness health contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.base import ApiSchema


class HealthComponentStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class DependencyHealthResponse(ApiSchema):
    name: str
    status: HealthComponentStatus
    checked_at: datetime
    latency_ms: float | None = Field(default=None, ge=0)
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkerHealthResponse(ApiSchema):
    worker_name: str
    queue_name: str
    status: HealthComponentStatus
    last_heartbeat_at: datetime | None
    age_seconds: float | None = Field(default=None, ge=0)


class SystemHealthResponse(ApiSchema):
    status: HealthComponentStatus
    checked_at: datetime
    dependencies: list[DependencyHealthResponse]
    workers: list[WorkerHealthResponse]


class LivenessResponse(ApiSchema):
    status: str = "ok"


class ReadinessResponse(ApiSchema):
    ready: bool
    status: HealthComponentStatus
