"""Short-lived in-memory Graph token cache with secret-free keys."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True, repr=False)
class GraphAccessToken:
    """A bearer token that deliberately never renders its secret in repr."""

    access_token: str
    expires_at: datetime

    def __repr__(self) -> str:
        return (
            "GraphAccessToken(access_token='<redacted>', "
            f"expires_at={self.expires_at!r})"
        )

    def is_usable(self, *, skew_seconds: int = 60) -> bool:
        now = datetime.now(UTC)
        expiry = (
            self.expires_at.replace(tzinfo=UTC)
            if self.expires_at.tzinfo is None
            else self.expires_at.astimezone(UTC)
        )
        return expiry > now + timedelta(seconds=max(0, skew_seconds))


class GraphTokenCache:
    """Concurrency-safe process-local cache for client-credential tokens."""

    def __init__(self) -> None:
        self._entries: dict[str, GraphAccessToken] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def make_key(
        *,
        tenant_id: str,
        client_id: str,
        scope: str,
        auth_mode: str,
    ) -> str:
        material = "\x1f".join(
            (
                tenant_id.strip().lower(),
                client_id.strip().lower(),
                scope.strip().lower(),
                auth_mode.strip().upper(),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> GraphAccessToken | None:
        async with self._lock:
            token = self._entries.get(key)
            if token is None:
                return None
            if not token.is_usable():
                self._entries.pop(key, None)
                return None
            return token

    async def set(self, key: str, token: GraphAccessToken) -> None:
        async with self._lock:
            self._entries[key] = token

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._entries.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
