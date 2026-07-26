"""Runtime notification composition, provider, and retry regressions."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings
from app.integrations.microsoft_graph.mail.graph_mail_service import (
    GraphMailService,
)
from app.models.dead_letter_job import DeadLetterJob
from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationEventType,
    NotificationRecipientType,
    NotificationSeverity,
)
from app.models.sharepoint_enums import DeadLetterStatus
from app.schemas.notification_internal import NotificationTaskPayload
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)
from app.services.notification.notification_retry_payload_store import (
    RedisNotificationRetryPayloadStore,
)
from app.services.notification.notification_retry_service import (
    NotificationRetryService,
)
from app.services.notification.notification_worker_service import (
    NotificationWorkerService,
)
from app.services.notification.provider_clients import (
    HttpTeamsWebhookClient,
    HttpTelegramBotClient,
)
from app.services.notification.runtime import create_notification_runtime
from app.services.secrets.encryption_service import AesGcmEncryptionService


class FakeGraphClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.closed = False

    async def post(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        expected_statuses: set[int],
    ) -> dict[str, Any]:
        self.posts.append(
            {
                "path": path,
                "payload": payload,
                "statuses": expected_statuses,
            }
        )
        return {}

    async def close(self) -> None:
        self.closed = True


class FakeRedisRetryClient:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
    ) -> bool:
        assert ex >= 300
        self.values[name] = value
        return True

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def exists(self, name: str) -> int:
        return int(name in self.values)

    async def delete(self, name: str) -> int:
        return int(self.values.pop(name, None) is not None)

    async def aclose(self) -> None:
        return None


class MemoryRetryStore:
    def __init__(self) -> None:
        self.values: dict[UUID, NotificationTaskPayload] = {}

    async def save(
        self,
        delivery_id: UUID,
        payload: NotificationTaskPayload,
    ) -> None:
        self.values[delivery_id] = payload

    async def resolve(
        self,
        *,
        session: AsyncSession,
        delivery_id: UUID,
    ) -> NotificationTaskPayload:
        del session
        return self.values[delivery_id]

    async def delete(self, delivery_id: UUID) -> None:
        self.values.pop(delivery_id, None)


class RecordingRetryPublisher:
    def __init__(self) -> None:
        self.deliveries: list[tuple[UUID, int]] = []

    async def publish(
        self,
        *,
        delivery_id: UUID,
        delay_seconds: int = 0,
    ) -> str:
        self.deliveries.append((delivery_id, delay_seconds))
        return "retry-task-id"


class RecordingNotificationCelery:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_task(
        self,
        name: str,
        *,
        args: list[str],
        countdown: int,
        queue: str,
    ) -> Any:
        self.calls.append(
            {
                "name": name,
                "args": args,
                "countdown": countdown,
                "queue": queue,
            }
        )
        return type("Task", (), {"id": "notification-retry-task"})()


class MutableTelegramChannel(BaseNotificationChannel):
    channel = NotificationChannel.TELEGRAM

    def __init__(self) -> None:
        self.succeed = False

    async def send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> DeliveryResult:
        if self.succeed:
            return DeliveryResult(
                succeeded=True,
                provider_message_id="telegram-message-id",
            )
        return DeliveryResult(
            succeeded=False,
            error_code="NOTIFICATION_TELEGRAM_SEND_FAILED",
            error_message="Provider unavailable.",
            retryable=True,
        )


def _payload() -> NotificationTaskPayload:
    return NotificationTaskPayload(
        event_type=NotificationEventType.SYSTEM_WORKER_UNAVAILABLE,
        channel=NotificationChannel.TELEGRAM,
        recipient_type=NotificationRecipientType.TELEGRAM_CHAT,
        recipient_reference="trusted-chat",
        subject="Worker unavailable",
        body="Private operational notification.",
        content_type=NotificationContentType.PLAIN_TEXT,
        severity=NotificationSeverity.CRITICAL,
    )


@pytest.mark.asyncio
async def test_graph_mail_service_uses_sendmail_and_closes_client() -> None:
    graph = FakeGraphClient()
    service = GraphMailService(
        cast(Settings, object()),
        graph_factory=lambda settings: cast(Any, graph),
    )
    provider_id = await service.send_mail(
        sender_user_id="sender@example.com",
        message={
            "subject": "Report ready",
            "body": {"contentType": "Text", "content": "Ready."},
            "toRecipients": [{"emailAddress": {"address": "recipient@example.com"}}],
        },
        client_request_id="request-123",
    )
    assert graph.posts[0]["path"] == ("/users/sender%40example.com/sendMail")
    assert graph.posts[0]["statuses"] == {202}
    assert graph.posts[0]["payload"]["saveToSentItems"] is True
    assert provider_id == "request-123"
    assert graph.closed is True


@pytest.mark.asyncio
async def test_http_provider_clients_use_bounded_mock_transports() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "hooks.example.test":
            return httpx.Response(
                202,
                headers={"request-id": "teams-request-id"},
            )
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 42}},
        )

    transport = httpx.MockTransport(handler)
    teams_id = await HttpTeamsWebhookClient(transport=transport).post_json(
        url="https://hooks.example.test/workflow",
        payload={"type": "message"},
        timeout_seconds=3,
    )
    telegram_id = await HttpTelegramBotClient(
        bot_token="123456:abcdefghijklmnopqrstuvwxyzABCD",
        transport=transport,
    ).send_message(chat_id="-100123", text="Alert")

    assert teams_id == "teams-request-id"
    assert telegram_id == "42"
    assert len(calls) == 2
    assert calls[0].url.scheme == "https"
    assert b"disable_web_page_preview" in calls[1].content


@pytest.mark.asyncio
async def test_redis_retry_payload_is_encrypted_and_rehydrated() -> None:
    values: dict[str, str] = {}
    cipher = AesGcmEncryptionService(
        {"v1": bytes(range(32))},
        active_key_version="v1",
    )
    store = RedisNotificationRetryPayloadStore(
        lambda: FakeRedisRetryClient(values),
        namespace="tests",
        ttl_seconds=600,
        cipher=cipher,
    )
    payload = _payload()
    delivery_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    await store.save(delivery_id, payload)

    serialized = next(iter(values.values()))
    assert serialized.startswith("enc:")
    assert payload.body not in serialized
    restored = await store.resolve(
        session=cast(AsyncSession, object()),
        delivery_id=delivery_id,
    )
    assert restored == payload
    assert await store.contains(delivery_id) is True
    await store.delete(delivery_id)
    assert await store.contains(delivery_id) is False


@pytest.mark.asyncio
async def test_runtime_composes_disabled_channels_and_bounded_retry(
    session_factory,
) -> None:
    values: dict[str, str] = {}
    celery = RecordingNotificationCelery()
    settings = get_settings().model_copy(
        update={
            "encryption_key": None,
            "notification_email_enabled": False,
            "notification_teams_enabled": False,
            "notification_telegram_enabled": False,
            "notification_max_retries": 3,
        }
    )
    runtime = create_notification_runtime(
        settings,
        celery=celery,
        redis_client_factory=lambda: FakeRedisRetryClient(values),
    )
    async with session_factory() as session:
        channels = runtime.worker_service.channel_factory(session)
        assert set(channels) == set(NotificationChannel)
        disabled = await channels[NotificationChannel.TELEGRAM].send(
            _payload().to_message()
        )
    assert disabled.error_code == "NOTIFICATION_CHANNEL_DISABLED"
    assert runtime.worker_service.maximum_attempts == 4

    delivery_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    await runtime.payload_store.save(delivery_id, _payload())
    provider_id = await runtime.retry_publisher.publish(
        delivery_id=delivery_id,
        delay_seconds=100_000,
    )
    assert provider_id == "notification-retry-task"
    assert celery.calls == [
        {
            "name": ("app.workers.notification_tasks.retry_failed_notification"),
            "args": [str(delivery_id)],
            "countdown": 86_400,
            "queue": settings.notification_queue_name,
        }
    ]


@pytest.mark.asyncio
async def test_worker_persists_schedules_rehydrates_and_exhausts_retry(
    session_factory,
) -> None:
    store = MemoryRetryStore()
    publisher = RecordingRetryPublisher()
    channel = MutableTelegramChannel()
    service = NotificationWorkerService(
        session_factory=session_factory,
        channel_factory=lambda session: {NotificationChannel.TELEGRAM: channel},
        retry_message_resolver=store,
        retry_payload_store=store,
        retry_publisher=publisher,
        maximum_attempts=2,
    )
    initial = await service.dispatch(_payload().model_dump(mode="json", by_alias=True))
    delivery_id = UUID(initial["deliveryId"])
    assert initial["status"] == "RETRY_SCHEDULED"
    assert delivery_id in store.values
    assert publisher.deliveries[0][0] == delivery_id

    retried = await service.retry(delivery_id)
    assert retried["status"] == "FAILED"
    assert delivery_id in store.values
    assert len(publisher.deliveries) == 1
    async with session_factory() as session:
        dead_letter = await session.scalar(
            select(DeadLetterJob).where(DeadLetterJob.entity_id == delivery_id)
        )
        assert dead_letter is not None
        assert dead_letter.status == DeadLetterStatus.ACTIVE

    channel.succeed = True
    async with session_factory() as session:
        queued = await NotificationRetryService(
            session,
            publisher=publisher,
        ).queue_manual_retry(delivery_id)
    assert queued.status.value == "RETRY_SCHEDULED"
    manually_retried = await service.retry(delivery_id)
    assert manually_retried["status"] == "SENT"
    assert len(publisher.deliveries) == 2
    assert delivery_id not in store.values
    async with session_factory() as session:
        dead_letter_count = int(
            await session.scalar(
                select(func.count())
                .select_from(DeadLetterJob)
                .where(DeadLetterJob.entity_id == delivery_id)
            )
            or 0
        )
        dead_letter_status = await session.scalar(
            select(DeadLetterJob.status).where(DeadLetterJob.entity_id == delivery_id)
        )
    assert dead_letter_count == 1
    assert dead_letter_status == DeadLetterStatus.RETRIED
