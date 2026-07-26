"""Service health endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.health import DependencyHealthData, HealthData
from app.services.health import HealthService, get_health_service

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.get(
    "",
    response_model=ApiResponse[HealthData],
    status_code=status.HTTP_200_OK,
    summary="Check API health",
)
async def health_check(
    settings: Configuration,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ApiResponse[HealthData]:
    """Return a lightweight liveness response without requiring the database."""
    return ApiResponse(
        success=True,
        message="Service is healthy.",
        data=service.get_health(version=settings.app_version),
        errors=None,
    )


@router.get(
    "/dependencies",
    response_model=ApiResponse[DependencyHealthData],
    status_code=status.HTTP_200_OK,
    summary="Check lightweight dependency readiness",
)
async def dependency_health_check(
    session: Session,
    settings: Configuration,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ApiResponse[DependencyHealthData]:
    """Report readiness without loading OCR, language, or similarity models."""
    return ApiResponse(
        success=True,
        message="Dependency readiness checked.",
        data=await service.get_dependency_health(
            session=session,
            settings=settings,
        ),
        errors=None,
    )
