"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.base import ApiSchema


class HealthData(BaseModel):
    """Stable health data contract consumed by Docker and the frontend."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy"] = "healthy"
    service: Literal["document-compliance-api"] = "document-compliance-api"
    version: str


class DependencyHealthData(ApiSchema):
    """Lightweight readiness state without loading inference models."""

    database: Literal["healthy", "unavailable"]
    redis: Literal["healthy", "unavailable"]
    extraction_worker: Literal["healthy", "unavailable"]
    ocr_worker: Literal["healthy", "unavailable"]
    language_worker: Literal["healthy", "unavailable"]
    ocr_provider: Literal["healthy", "unavailable"]
    language_model: Literal["healthy", "unavailable"]
