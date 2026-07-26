"""Detailed production dependency and worker health endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.system_health import (
    LivenessResponse,
    ReadinessResponse,
    SystemHealthResponse,
)
from app.services.system_health_service import (
    DependencyProbe,
    SystemHealthService,
)

EXPECTED_WORKERS = (
    "extraction",
    "ocr",
    "language",
    "compliance",
    "similarity",
    "glossary",
    "revision",
    "reporting",
    "sharepoint",
    "notifications",
    "maintenance",
)

router = APIRouter(tags=["System Health"])
public_router = APIRouter(tags=["Health"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
HealthViewer = Annotated[
    User,
    Depends(require_permissions("system_health:view")),
]


async def _database_probe(session: AsyncSession) -> dict[str, object]:
    await session.execute(text("SELECT 1"))
    return {"connected": True}


def get_additional_health_probes() -> Sequence[DependencyProbe]:
    """Override with Redis, storage, Graph, and configuration probes."""

    return ()


AdditionalProbes = Annotated[
    Sequence[DependencyProbe],
    Depends(get_additional_health_probes),
]


def _service(
    session: AsyncSession,
    additional_probes: Sequence[DependencyProbe],
) -> SystemHealthService:
    async def database_check() -> dict[str, object]:
        return await _database_probe(session)

    return SystemHealthService(
        session,
        probes=(
            DependencyProbe(name="database", check=database_check),
            *additional_probes,
        ),
        expected_workers=EXPECTED_WORKERS,
    )


@router.get(
    "/health/dependencies",
    response_model=ApiResponse[SystemHealthResponse],
)
@router.get(
    "/system-health",
    response_model=ApiResponse[SystemHealthResponse],
)
@router.get(
    "/admin/system-health",
    response_model=ApiResponse[SystemHealthResponse],
)
async def dependency_and_worker_health(
    session: Session,
    user: HealthViewer,
    additional_probes: AdditionalProbes,
) -> ApiResponse[SystemHealthResponse]:
    result = await _service(session, additional_probes).health()
    return ApiResponse(
        success=True,
        message="System dependency health checked.",
        data=result,
        errors=None,
    )


@public_router.get(
    "/health/live",
    response_model=LivenessResponse,
)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@public_router.get(
    "/health/ready",
    response_model=ReadinessResponse,
)
async def readiness(
    session: Session,
    additional_probes: AdditionalProbes,
    response: Response,
) -> ReadinessResponse:
    result = await _service(session, additional_probes).readiness()
    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
