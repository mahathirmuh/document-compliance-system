"""Service health endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.schemas.common import ApiResponse
from app.schemas.health import HealthData
from app.services.health import HealthService, get_health_service

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[HealthData],
    status_code=status.HTTP_200_OK,
    summary="Check API health",
)
async def health_check(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ApiResponse[HealthData]:
    """Return a lightweight liveness response without requiring the database."""
    return ApiResponse(
        success=True,
        message="Service is healthy.",
        data=service.get_health(),
        errors=None,
    )
