"""Production composition for notification channels and bounded retries."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.microsoft_graph.mail.graph_mail_service import (
    GraphClientFactory,
    GraphMailService,
)
from app.models.notification_enums import NotificationChannel
from app.repositories.in_app_notification_repository import (
    InAppNotificationRepository,
)
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.channels.graph_email_notification_channel import (
    GraphEmailNotificationChannel,
)
from app.services.notification.channels.in_app_notification_channel import (
    InAppNotificationChannel,
)
from app.services.notification.channels.teams_notification_channel import (
    TeamsNotificationChannel,
)
from app.services.notification.channels.telegram_notification_channel import (
    TelegramNotificationChannel,
)
from app.services.notification.notification_retry_payload_store import (
    RedisNotificationRetryPayloadStore,
    RedisRetryClient,
    RedisRetryClientFactory,
)
from app.services.notification.notification_worker_service import (
    NotificationChannelFactory,
    NotificationWorkerService,
)
from app.services.notification.provider_clients import (
    HttpTeamsWebhookClient,
    HttpTelegramBotClient,
)
from app.services.secrets.encryption_service import (
    AesGcmEncryptionService,
    EncryptionError,
)
from app.services.sharepoint.graph_factory import create_graph_client

_RETRY_TASK = "app.workers.notification_tasks.retry_failed_notification"


class CelerySender(Protocol):
    def send_task(
        self,
        name: str,
        *,
        args: list[str],
        countdown: int,
        queue: str,
    ) -> Any: ...


class CeleryNotificationRetryPublisher:
    def __init__(
        self,
        celery: CelerySender,
        *,
        payload_store: RedisNotificationRetryPayloadStore,
        queue_name: str,
    ) -> None:
        self.celery = celery
        self.payload_store = payload_store
        self.queue_name = queue_name

    async def publish(
        self,
        *,
        delivery_id: UUID,
        delay_seconds: int = 0,
    ) -> str | None:
        if not await self.payload_store.contains(delivery_id):
            raise RuntimeError("Notification retry payload is unavailable or expired.")
        task = self.celery.send_task(
            _RETRY_TASK,
            args=[str(delivery_id)],
            countdown=max(0, min(int(delay_seconds), 24 * 60 * 60)),
            queue=self.queue_name,
        )
        task_id = getattr(task, "id", None)
        return str(task_id)[:1000] if task_id else None


@dataclass(frozen=True, slots=True)
class NotificationRuntime:
    worker_service: NotificationWorkerService
    retry_publisher: CeleryNotificationRetryPublisher
    payload_store: RedisNotificationRetryPayloadStore


def create_notification_runtime(
    settings: Settings,
    *,
    celery: CelerySender,
    redis_client_factory: RedisRetryClientFactory | None = None,
    graph_factory: GraphClientFactory = create_graph_client,
    teams_client: HttpTeamsWebhookClient | None = None,
    telegram_client: HttpTelegramBotClient | None = None,
) -> NotificationRuntime:
    retry_store = RedisNotificationRetryPayloadStore(
        redis_client_factory or _redis_factory(settings),
        namespace=settings.redis_key_prefix,
        ttl_seconds=max(
            settings.celery_result_expires_seconds,
            settings.notification_task_time_limit_seconds * 2,
        ),
        cipher=_retry_cipher(settings),
    )
    retry_publisher = CeleryNotificationRetryPublisher(
        celery,
        payload_store=retry_store,
        queue_name=settings.notification_queue_name,
    )
    channel_factory = _channel_factory(
        settings,
        graph_factory=graph_factory,
        teams_client=teams_client,
        telegram_client=telegram_client,
    )
    return NotificationRuntime(
        worker_service=NotificationWorkerService(
            channel_factory=channel_factory,
            retry_message_resolver=retry_store,
            retry_payload_store=retry_store,
            retry_publisher=retry_publisher,
            maximum_attempts=settings.notification_max_retries + 1,
        ),
        retry_publisher=retry_publisher,
        payload_store=retry_store,
    )


def _channel_factory(
    settings: Settings,
    *,
    graph_factory: GraphClientFactory,
    teams_client: HttpTeamsWebhookClient | None,
    telegram_client: HttpTelegramBotClient | None,
) -> NotificationChannelFactory:
    graph_mail = GraphMailService(settings, graph_factory=graph_factory)
    resolved_teams_client = teams_client or HttpTeamsWebhookClient()
    telegram_token = _secret(settings.telegram_bot_token)
    resolved_telegram_client = telegram_client or HttpTelegramBotClient(
        bot_token=telegram_token or "",
    )
    teams_webhook_url = _secret(settings.notification_teams_webhook_url) or ""

    def factory(
        session: AsyncSession,
    ) -> Mapping[NotificationChannel, BaseNotificationChannel]:
        return {
            NotificationChannel.IN_APP: InAppNotificationChannel(
                InAppNotificationRepository(session)
            ),
            NotificationChannel.EMAIL_GRAPH: GraphEmailNotificationChannel(
                graph_mail,
                enabled=settings.notification_email_enabled,
                sender_user_id=(settings.notification_email_sender_user_id or ""),
                reply_to=(
                    str(settings.notification_email_reply_to)
                    if settings.notification_email_reply_to is not None
                    else None
                ),
                maximum_recipients=(settings.notification_email_max_recipients),
            ),
            NotificationChannel.TEAMS: TeamsNotificationChannel(
                resolved_teams_client,
                enabled=settings.notification_teams_enabled,
                mode=settings.notification_teams_mode,
                webhook_url=teams_webhook_url,
            ),
            NotificationChannel.TELEGRAM: TelegramNotificationChannel(
                resolved_telegram_client,
                enabled=settings.notification_telegram_enabled,
                default_chat_id=settings.telegram_default_chat_id,
            ),
        }

    return factory


def _redis_factory(settings: Settings) -> RedisRetryClientFactory:
    password = _secret(settings.redis_password)

    def factory() -> RedisRetryClient:
        return cast(
            RedisRetryClient,
            Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=password,
                ssl=settings.redis_ssl,
                socket_timeout=settings.redis_socket_timeout_seconds,
                socket_connect_timeout=(
                    settings.redis_socket_connect_timeout_seconds
                ),
                health_check_interval=(
                    settings.redis_health_check_interval_seconds
                ),
                max_connections=settings.redis_max_connections,
                decode_responses=False,
            ),
        )

    return factory


def _retry_cipher(settings: Settings) -> AesGcmEncryptionService | None:
    encoded = _secret(settings.encryption_key)
    if not encoded:
        return None
    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EncryptionError("Encryption key encoding is invalid.") from exc
    return AesGcmEncryptionService(
        {settings.encryption_key_version: key},
        active_key_version=settings.encryption_key_version,
    )


def _secret(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None
