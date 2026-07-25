"""Health API contract tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_exact_contract() -> None:
    expected = {
        "success": True,
        "message": "Service is healthy.",
        "data": {
            "status": "healthy",
            "service": "document-compliance-api",
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
