"""Health-check application service."""

from app.schemas.health import HealthData


class HealthService:
    """Build the API liveness representation."""

    def get_health(self) -> HealthData:
        return HealthData()


def get_health_service() -> HealthService:
    """FastAPI dependency provider for the health service."""
    return HealthService()
