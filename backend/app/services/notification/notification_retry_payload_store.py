"""Short-lived, optionally encrypted notification retry payload storage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.notification_internal import NotificationTaskPayload
from app.services.secrets.encryption_service import AesGcmEncryptionService


class RedisRetryClient(Protocol):
    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
    ) -> object: ...

    async def get(self, name: str) -> object: ...

    async def exists(self, name: str) -> object: ...

    async def delete(self, name: str) -> object: ...

    async def aclose(self) -> None: ...


RedisRetryClientFactory = Callable[[], RedisRetryClient]


class RedisNotificationRetryPayloadStore:
    """Keep rendered payloads out of delivery/audit rows and expire them."""

    def __init__(
        self,
        client_factory: RedisRetryClientFactory,
        *,
        namespace: str,
        ttl_seconds: int,
        cipher: AesGcmEncryptionService | None = None,
    ) -> None:
        normalized_namespace = namespace.strip().strip(":")
        if not normalized_namespace or len(normalized_namespace) > 200:
            raise ValueError("Retry payload namespace is invalid.")
        self.client_factory = client_factory
        self.namespace = normalized_namespace
        self.ttl_seconds = max(300, min(ttl_seconds, 30 * 24 * 60 * 60))
        self.cipher = cipher

    async def save(
        self,
        delivery_id: UUID,
        payload: NotificationTaskPayload,
    ) -> None:
        serialized = payload.model_dump_json(by_alias=True)
        value = (
            f"enc:{self.cipher.encrypt(serialized)}"
            if self.cipher is not None
            else f"json:{serialized}"
        )
        client = self.client_factory()
        try:
            await client.set(
                self._key(delivery_id),
                value,
                ex=self.ttl_seconds,
            )
        finally:
            await client.aclose()

    async def resolve(
        self,
        *,
        session: AsyncSession,
        delivery_id: UUID,
    ) -> NotificationTaskPayload:
        del session
        raw = await self._get(delivery_id)
        if raw is None:
            raise RuntimeError("Notification retry payload is unavailable or expired.")
        if raw.startswith("enc:"):
            if self.cipher is None:
                raise RuntimeError(
                    "Notification retry payload encryption is unavailable."
                )
            serialized = self.cipher.decrypt(raw.removeprefix("enc:"))
        elif raw.startswith("json:"):
            serialized = raw.removeprefix("json:")
        else:
            raise RuntimeError("Notification retry payload format is invalid.")
        return NotificationTaskPayload.model_validate_json(serialized)

    async def contains(self, delivery_id: UUID) -> bool:
        client = self.client_factory()
        try:
            return bool(await client.exists(self._key(delivery_id)))
        finally:
            await client.aclose()

    async def delete(self, delivery_id: UUID) -> None:
        client = self.client_factory()
        try:
            await client.delete(self._key(delivery_id))
        finally:
            await client.aclose()

    async def _get(self, delivery_id: UUID) -> str | None:
        client = self.client_factory()
        try:
            raw: Any = await client.get(self._key(delivery_id))
        finally:
            await client.aclose()
        if raw is None:
            return None
        if isinstance(raw, bytes):
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RuntimeError(
                    "Notification retry payload encoding is invalid."
                ) from exc
        if not isinstance(raw, str):
            raise RuntimeError("Notification retry payload type is invalid.")
        return raw

    def _key(self, delivery_id: UUID) -> str:
        return f"{self.namespace}:notification-retry:{delivery_id}"
