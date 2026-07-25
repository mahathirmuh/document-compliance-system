"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthData(BaseModel):
    """Stable health data contract consumed by Docker and the frontend."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy"] = "healthy"
    service: Literal["document-compliance-api"] = "document-compliance-api"
