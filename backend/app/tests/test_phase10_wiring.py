"""Integration wiring checks for Phase 10 routers, queues, and correlation."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.system_health import EXPECTED_WORKERS
from app.core.config import Settings
from app.core.request_id import current_request_id, request_id_context
from app.integrations.microsoft_graph.graph_request_service import (
    GraphRequestService,
)
from app.integrations.microsoft_graph.graph_retry_policy import GraphRetryPolicy
from app.main import app
from app.workers.celery_app import celery_app
from app.workers.task_correlation_signals import (
    activate_task_request_id,
    add_request_id_to_task_headers,
    clear_task_request_id,
)
from app.workers.worker_heartbeat_signals import _identity


class _TokenProvider:
    async def get_access_token(
        self,
        *,
        force_refresh: bool = False,
    ) -> str:
        del force_refresh
        return "mock-token"


def test_phase10_openapi_and_celery_wiring() -> None:
    paths = set(app.openapi()["paths"])
    assert {
        "/api/v1/integrations/sharepoint/connections",
        "/api/v1/integrations/microsoft-graph/webhook",
        "/api/v1/sharepoint/sync-profiles",
        "/api/v1/sharepoint/sync-jobs",
        "/api/v1/sharepoint/conflicts",
        "/api/v1/notifications",
        "/api/v1/admin/retention-policies",
        "/api/v1/admin/dead-letter-jobs",
        "/api/v1/admin/system-health",
        "/health/live",
        "/health/ready",
    }.issubset(paths)

    queue_names = {queue.name for queue in celery_app.conf.task_queues}
    assert queue_names == {
        "extraction",
        "ocr",
        "language",
        "compliance",
        "similarity",
        "glossary",
        "revision-comparison",
        "reporting",
        "sharepoint",
        "notifications",
        "maintenance",
    }
    assert set(EXPECTED_WORKERS) == {
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
    }
    includes = set(celery_app.conf.include)
    assert {
        "app.workers.sharepoint_tasks",
        "app.workers.notification_tasks",
        "app.workers.maintenance_tasks",
    }.issubset(includes)
    assert "renew-graph-subscriptions-hourly" in celery_app.conf.beat_schedule
    assert "cleanup-deleted-files" in celery_app.conf.beat_schedule


@pytest.mark.asyncio
async def test_graph_propagates_one_http_correlation_id_across_retries() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                503,
                json={"error": {"code": "serviceNotAvailable"}},
            )
        return httpx.Response(200, json={"ok": True})

    async def no_sleep(_: float) -> None:
        return None

    token = request_id_context.set("phase10-http-request")
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            service = GraphRequestService(
                auth_provider=_TokenProvider(),
                http_client=http_client,
                retry_policy=GraphRetryPolicy(
                    maximum_retries=1,
                    base_seconds=0.1,
                    maximum_seconds=1,
                    jitter_ratio=0,
                ),
                sleep=no_sleep,
            )
            response = await service.request("GET", "/sites/example")
            await response.aclose()
    finally:
        request_id_context.reset(token)

    assert len(requests) == 2
    assert {
        request.headers["client-request-id"] for request in requests
    } == {"phase10-http-request"}


def test_celery_correlation_and_worker_identity() -> None:
    outer = request_id_context.set("phase10-publisher")
    headers: dict[str, object] = {}
    try:
        add_request_id_to_task_headers(headers=headers)
    finally:
        request_id_context.reset(outer)

    task_id = "phase10-task"
    task = SimpleNamespace(request=SimpleNamespace(headers=headers))
    activate_task_request_id(task_id=task_id, task=task)
    assert current_request_id() == "phase10-publisher"
    clear_task_request_id(task_id=task_id)
    assert current_request_id() is None

    assert _identity(
        SimpleNamespace(
            eventer=SimpleNamespace(hostname="sharepoint@worker-1")
        )
    ) == ("sharepoint", "sharepoint@worker-1", "sharepoint")
    assert _identity("maintenance@worker-2") == (
        "maintenance",
        "maintenance@worker-2",
        "maintenance",
    )


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": (
            "postgresql+asyncpg://document:password@postgres:5432/document"
        ),
        "jwt_secret_key": "production-test-jwt-key-at-least-thirty-two-chars",
        "public_app_url": "https://documents.example.test",
        "api_base_url": "https://documents.example.test/api",
        "cors_origins": '["https://documents.example.test"]',
        "trusted_hosts": "documents.example.test",
        # Deterministic non-secret AES fixture; never use outside tests.
        "encryption_key": (
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="  # gitleaks:allow
        ),
        "log_format": "json",
        "redis_password": "production-test-redis-password",
        "redis_key_prefix": "document-compliance:production-test",
        "celery_broker_url": (
            "redis://:production-test-redis-password@redis:6379/0"
        ),
        "celery_result_backend": (
            "redis://:production-test-redis-password@redis:6379/1"
        ),
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_requires_authenticated_redis_and_aes_key() -> None:
    settings = _production_settings()
    assert settings.environment == "production"

    with pytest.raises(ValidationError, match="REDIS_PASSWORD"):
        _production_settings(redis_password=None)
    with pytest.raises(ValidationError, match="include authentication"):
        _production_settings(celery_broker_url="redis://redis:6379/0")
    with pytest.raises(ValidationError, match="valid base64"):
        _production_settings(encryption_key="not-base64")
