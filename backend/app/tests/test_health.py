"""Health API contract tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.health import DependencyHealthData
from app.services.health import get_health_service


class _ReadyHealthService:
    async def get_dependency_health(self, **_: object) -> DependencyHealthData:
        return DependencyHealthData(
            database="healthy",
            redis="healthy",
            extraction_worker="healthy",
            ocr_worker="healthy",
            language_worker="healthy",
            compliance_worker="healthy",
            ocr_provider="healthy",
            language_model="healthy",
            similarity_model="healthy",
            glossary_service="healthy",
            revision_comparison_worker="healthy",
            reporting_worker="healthy",
        )


@pytest.mark.asyncio
async def test_health_endpoint_returns_exact_contract() -> None:
    expected = {
        "success": True,
        "message": "Service is healthy.",
        "data": {
            "status": "healthy",
            "service": "document-compliance-api",
            "version": "0.9.0",
        },
        "errors": None,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.asyncio
async def test_unknown_endpoint_uses_safe_error_envelope() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "message": "Not Found",
        "data": None,
        "errors": None,
    }


@pytest.mark.asyncio
async def test_dependency_health_is_camel_case_and_does_not_expose_paths(
    api_client: AsyncClient,
) -> None:
    app.dependency_overrides[get_health_service] = _ReadyHealthService

    response = await api_client.get("/api/v1/health/dependencies")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Dependency readiness checked.",
        "data": {
            "database": "healthy",
            "redis": "healthy",
            "extractionWorker": "healthy",
            "ocrWorker": "healthy",
            "languageWorker": "healthy",
            "complianceWorker": "healthy",
            "ocrProvider": "healthy",
            "languageModel": "healthy",
            "similarityModel": "healthy",
            "glossaryService": "healthy",
            "revisionComparisonWorker": "healthy",
            "reportingWorker": "healthy",
        },
        "errors": None,
    }
