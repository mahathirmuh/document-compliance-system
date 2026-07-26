"""Focused production-hardening, retention, and recovery tests."""

from __future__ import annotations

import base64
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.log_redaction import REDACTED, redact_sensitive
from app.core.request_id import RequestIdMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.models.data_retention_policy import (
    DataRetentionPolicy,
    RetentionEntityType,
    RetentionScopeType,
)
from app.models.sharepoint_enums import DeadLetterStatus
from app.models.worker_heartbeat import WorkerHeartbeatState
from app.observability.metrics import create_default_registry
from app.observability.metrics_endpoint import create_metrics_router
from app.services.maintenance.dead_letter_service import DeadLetterService
from app.services.retention.contracts import RetentionCandidate
from app.services.retention.retention_service import RetentionService
from app.services.secrets.encryption_service import (
    AesGcmEncryptionService,
    DecryptionError,
)
from app.services.security.rate_limiter import (
    RateLimitRule,
    RedisRateLimiter,
)
from app.services.security_scanning.base_malware_scanner import (
    MalwareScannerFailPolicy,
    MalwareScanStatus,
)
from app.services.security_scanning.clamav_malware_scanner import (
    ClamAvMalwareScanner,
)
from app.services.system_health_service import (
    DependencyProbe,
    SystemHealthService,
)
from app.services.worker_heartbeat_service import WorkerHeartbeatService
from app.utils.datetime import utc_now
from scripts import rotate_encrypted_secrets as rotation_script


class FakeRedis:
    def __init__(self, result: object) -> None:
        self.result = result
        self.arguments: tuple[object, ...] | None = None

    async def eval(
        self,
        script: str,
        number_of_keys: int,
        *keys_and_args: object,
    ) -> object:
        self.arguments = (script, number_of_keys, *keys_and_args)
        return self.result


class FakeRetentionHandler:
    supports_archive = True
    supports_soft_delete = True

    def __init__(self, candidates: list[RetentionCandidate]) -> None:
        self.candidates = candidates
        self.archived: list[RetentionCandidate] = []
        self.soft_deleted: list[RetentionCandidate] = []
        self.permanently_deleted: list[RetentionCandidate] = []

    async def list_candidates(self, **_: Any) -> list[RetentionCandidate]:
        return self.candidates

    async def archive(self, candidate: RetentionCandidate) -> None:
        self.archived.append(candidate)

    async def soft_delete(self, candidate: RetentionCandidate) -> None:
        self.soft_deleted.append(candidate)

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None:
        self.permanently_deleted.append(candidate)


class FakeDeadLetterPublisher:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] | None = None

    async def publish(
        self,
        *,
        task_name: str,
        arguments: dict[str, Any],
        dead_letter_job_id,
    ) -> str:
        self.arguments = {
            "taskName": task_name,
            "arguments": arguments,
            "jobId": str(dead_letter_job_id),
        }
        return "queued-dead-letter-retry"


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeRotationSession:
    def __init__(self, row: SimpleNamespace) -> None:
        self.row = row
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    def begin(self) -> _AsyncContext:
        return _AsyncContext()

    async def scalars(self, statement) -> list[SimpleNamespace]:
        self.calls += 1
        return [self.row] if self.calls == 1 else []


def test_recursive_log_redaction_covers_nested_values_and_urls() -> None:
    value = {
        "authorization": "Bearer top-secret",
        "nested": {
            "client_secret": "credential",
            "safe": "https://example.test/path?token=value&mode=safe",
            "message": "database postgresql://user:password@example.test/app",
        },
        "items": [{"password": "secret-password"}],
    }
    result = redact_sensitive(value)
    assert result["authorization"] == REDACTED
    assert result["nested"]["client_secret"] == REDACTED
    assert "value" not in result["nested"]["safe"]
    assert "password@" not in result["nested"]["message"]
    assert result["items"][0]["password"] == REDACTED


@pytest.mark.asyncio
async def test_request_id_and_security_headers_are_bounded() -> None:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware,
        production=True,
    )
    app.add_middleware(RequestIdMiddleware)

    @app.get("/api/test")
    async def test_route() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
    ) as client:
        response = await client.get(
            "/api/test",
            headers={"X-Request-ID": "x" * 500},
        )
    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 36
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "unsafe-eval" not in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_redis_rate_limiter_hashes_principal_and_denies_over_limit() -> None:
    redis = FakeRedis([11, 42])
    limiter = RedisRateLimiter(redis, namespace="test", enabled=True)
    decision = await limiter.check(
        RateLimitRule(name="login", limit=10, window_seconds=60),
        principal="private-user@example.com:127.0.0.1",
    )
    assert decision.allowed is False
    assert decision.retry_after_seconds == 42
    assert redis.arguments is not None
    redis_key = str(redis.arguments[2])
    assert "private-user@example.com" not in redis_key


def test_aes_gcm_round_trip_and_wrong_key() -> None:
    pytest.importorskip("cryptography")
    first_key = bytes(range(32))
    second_key = bytes(reversed(range(32)))
    service = AesGcmEncryptionService(
        {"v1": first_key},
        active_key_version="v1",
    )
    encrypted = service.encrypt("sensitive delta link")
    assert "sensitive delta link" not in encrypted
    assert service.decrypt(encrypted) == "sensitive delta link"

    wrong_service = AesGcmEncryptionService(
        {"v1": second_key},
        active_key_version="v1",
    )
    with pytest.raises(DecryptionError) as caught:
        wrong_service.decrypt(encrypted)
    assert caught.value.code == "DECRYPTION_FAILED"

    encoded = base64.b64encode(first_key).decode()
    assert len(base64.b64decode(encoded)) == 32


def test_clamav_response_parser_and_fail_policy() -> None:
    scanner = ClamAvMalwareScanner(
        host="clamav",
        fail_policy=MalwareScannerFailPolicy.FAIL_CLOSED,
    )
    clean = scanner.parse_response(b"stream: OK\x00")
    infected = scanner.parse_response(b"stream: Eicar-Test-Signature FOUND\x00")
    unavailable = scanner.parse_response(b"stream: scanner error\x00")
    assert clean.status == MalwareScanStatus.CLEAN
    assert clean.allowed is True
    assert infected.status == MalwareScanStatus.INFECTED
    assert infected.allowed is False
    assert infected.signature == "Eicar-Test-Signature"
    assert unavailable.status == MalwareScanStatus.UNAVAILABLE
    assert unavailable.allowed is False


def test_clamav_fail_open_is_explicit_and_warns() -> None:
    scanner = ClamAvMalwareScanner(
        host="clamav",
        fail_policy=MalwareScannerFailPolicy.FAIL_OPEN_WITH_WARNING,
    )
    unavailable = scanner.parse_response(b"stream: scanner error\x00")
    assert unavailable.status == MalwareScanStatus.UNAVAILABLE
    assert unavailable.allowed is True
    assert unavailable.error_code == "MALWARE_SCANNER_UNAVAILABLE"
    assert unavailable.warning


@pytest.mark.asyncio
async def test_key_rotation_dry_run_authenticates_without_mutating(
    monkeypatch,
) -> None:
    pytest.importorskip("cryptography")
    old_key = bytes(range(32))
    new_key = bytes(reversed(range(32)))
    old_cipher = AesGcmEncryptionService(
        {"old": old_key},
        active_key_version="old",
    )
    original_envelope = old_cipher.encrypt("sensitive delta cursor")
    row = SimpleNamespace(
        id=uuid4(),
        delta_link_encrypted=original_envelope,
    )
    fake_session = FakeRotationSession(row)
    monkeypatch.setattr(
        rotation_script,
        "AsyncSessionFactory",
        lambda: fake_session,
    )
    monkeypatch.setenv("TEST_ROTATION_OLD_KEY", base64.b64encode(old_key).decode())
    monkeypatch.setenv("TEST_ROTATION_NEW_KEY", base64.b64encode(new_key).decode())

    summary = await rotation_script.rotate(
        rotation_script.RotationArguments(
            old_key_environment_name="TEST_ROTATION_OLD_KEY",
            old_key_version="old",
            new_key_environment_name="TEST_ROTATION_NEW_KEY",
            new_key_version="new",
            dry_run=True,
            batch_size=10,
        )
    )
    assert summary == {
        "dryRun": True,
        "scanned": 1,
        "rotated": 1,
        "alreadyCurrent": 0,
        "failed": 0,
    }
    assert row.delta_link_encrypted == original_envelope


@pytest.mark.asyncio
async def test_metrics_reject_unbounded_channel_label() -> None:
    registry = create_default_registry()
    with pytest.raises(ValueError, match="bounded set"):
        await registry.increment(
            "document_compliance_notification_deliveries_total",
            labels={"channel": str(uuid4()), "outcome": "success"},
        )


@pytest.mark.asyncio
async def test_metrics_endpoint_can_require_constant_time_token() -> None:
    registry = create_default_registry()
    app = FastAPI()
    app.include_router(create_metrics_router(registry, access_token="metrics-secret"))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        denied = await client.get("/metrics")
        allowed = await client.get(
            "/metrics",
            headers={"X-Metrics-Token": "metrics-secret"},
        )
    assert denied.status_code == 404
    assert allowed.status_code == 200
    assert "# TYPE document_compliance_http_requests_total counter" in (allowed.text)


@pytest.mark.asyncio
async def test_retention_dry_run_honors_legal_hold_and_sole_copy(
    session_factory,
) -> None:
    now = utc_now()
    candidates = [
        RetentionCandidate(
            id=uuid4(),
            created_at=now - timedelta(days=60),
        ),
        RetentionCandidate(
            id=uuid4(),
            created_at=now - timedelta(days=60),
            legal_hold=True,
        ),
        RetentionCandidate(
            id=uuid4(),
            created_at=now - timedelta(days=60),
            sole_copy=True,
        ),
    ]
    handler = FakeRetentionHandler(candidates)
    async with session_factory() as session:
        session.add(
            DataRetentionPolicy(
                name="Notification cleanup",
                entity_type=RetentionEntityType.NOTIFICATION,
                scope_type=RetentionScopeType.GLOBAL,
                retention_days=30,
                delete_after_days=30,
                legal_hold_enabled=False,
                is_active=True,
            )
        )
        await session.commit()

    async with session_factory() as session:
        preview = await RetentionService(
            session,
            handlers={RetentionEntityType.NOTIFICATION: handler},
        ).run(
            entity_type=RetentionEntityType.NOTIFICATION,
            dry_run=True,
            batch_size=100,
        )
    assert preview.scanned_count == 3
    assert preview.eligible_count == 1
    assert preview.legal_hold_skipped_count == 1
    assert handler.soft_deleted == []
    assert preview.warnings


@pytest.mark.asyncio
async def test_worker_readiness_requires_fresh_active_heartbeat(
    session_factory,
) -> None:
    async def healthy_probe() -> dict[str, bool]:
        return {"connected": True}

    async with session_factory() as session:
        await WorkerHeartbeatService(session).beat(
            worker_name="notifications",
            worker_instance="worker-1",
            queue_name="notifications",
        )
        health = SystemHealthService(
            session,
            probes=[DependencyProbe(name="database", check=healthy_probe)],
            expected_workers=["notifications"],
            worker_stale_seconds=120,
        )
        assert (await health.readiness()).ready is True

        await WorkerHeartbeatService(session).beat(
            worker_name="notifications",
            worker_instance="worker-1",
            queue_name="notifications",
            state=WorkerHeartbeatState.STOPPED,
        )
        assert (await health.readiness()).ready is False


@pytest.mark.asyncio
async def test_dead_letter_retry_uses_only_sanitized_arguments(
    session_factory,
) -> None:
    publisher = FakeDeadLetterPublisher()
    async with session_factory() as session:
        service = DeadLetterService(session, publisher=publisher)
        job = await service.record(
            task_name="app.workers.retry_sync",
            entity_type="SharePointSyncJob",
            entity_id=uuid4(),
            attempts=5,
            maximum_attempts=5,
            arguments={
                "profileId": str(uuid4()),
                "authorization": "Bearer secret-token",
                "callback": "https://example.test/hook?token=secret-value",
                "nested": {"client_secret": "secret-client-value"},
            },
            error_code="GRAPH_SERVICE_UNAVAILABLE",
            safe_error="Graph service is temporarily unavailable.",
        )
        result = await service.retry(job.id)
    assert result.status == DeadLetterStatus.RETRY_QUEUED
    assert publisher.arguments is not None
    serialized = str(publisher.arguments)
    assert "secret-token" not in serialized
    assert "secret-value" not in serialized
    assert "secret-client-value" not in serialized
