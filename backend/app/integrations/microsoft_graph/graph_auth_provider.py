"""MSAL-backed OAuth 2.0 client-credentials provider."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.integrations.microsoft_graph.graph_token_cache import (
    GraphAccessToken,
    GraphTokenCache,
)

GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"


class ConfidentialClient(Protocol):
    def acquire_token_for_client(
        self,
        scopes: list[str],
    ) -> dict[str, Any]: ...


class GraphAuthenticationError(RuntimeError):
    """Safe authentication failure; upstream details are intentionally hidden."""

    code = "GRAPH_AUTHENTICATION_FAILED"


@dataclass(frozen=True, slots=True, repr=False)
class GraphAuthConfig:
    tenant_id: str
    client_id: str
    auth_mode: str = "CLIENT_SECRET"
    client_secret: str | None = None
    certificate_path: Path | None = None
    certificate_password: str | None = None
    scope: str = GRAPH_DEFAULT_SCOPE
    token_cache_ttl_seconds: int = 3000

    def __post_init__(self) -> None:
        mode = self.auth_mode.strip().upper()
        if not self.tenant_id.strip() or not self.client_id.strip():
            raise ValueError("Microsoft tenant and client identifiers are required.")
        if mode not in {"CLIENT_SECRET", "CERTIFICATE"}:
            raise ValueError("Graph auth mode must be CLIENT_SECRET or CERTIFICATE.")
        if mode == "CLIENT_SECRET" and not self.client_secret:
            raise ValueError("A client secret is required for CLIENT_SECRET mode.")
        if mode == "CERTIFICATE" and self.certificate_path is None:
            raise ValueError("A certificate path is required for CERTIFICATE mode.")
        if self.token_cache_ttl_seconds <= 0:
            raise ValueError("Token cache TTL must be positive.")
        object.__setattr__(self, "auth_mode", mode)

    def __repr__(self) -> str:
        return (
            "GraphAuthConfig("
            f"tenant_id={self.tenant_id!r}, client_id={self.client_id!r}, "
            f"auth_mode={self.auth_mode!r}, client_secret='<redacted>', "
            f"certificate_path={self.certificate_path!r}, "
            "certificate_password='<redacted>')"
        )


class MsalGraphAuthProvider:
    """Acquire app-only tokens and cache them without database persistence."""

    def __init__(
        self,
        config: GraphAuthConfig,
        *,
        token_cache: GraphTokenCache | None = None,
        client_factory: Callable[[GraphAuthConfig], ConfidentialClient]
        | None = None,
    ) -> None:
        self.config = config
        self.cache = token_cache or GraphTokenCache()
        self._client_factory = client_factory or self._build_msal_client
        self._client: ConfidentialClient | None = None
        self._acquire_lock = asyncio.Lock()
        self._cache_key = self.cache.make_key(
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            scope=config.scope,
            auth_mode=config.auth_mode,
        )

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = await self.cache.get(self._cache_key)
            if cached is not None:
                return cached.access_token

        async with self._acquire_lock:
            if not force_refresh:
                cached = await self.cache.get(self._cache_key)
                if cached is not None:
                    return cached.access_token
            if force_refresh:
                await self.cache.invalidate(self._cache_key)
            client = self._client or self._client_factory(self.config)
            self._client = client
            result = await asyncio.to_thread(
                client.acquire_token_for_client,
                scopes=[self.config.scope],
            )
            raw_token = result.get("access_token")
            if not isinstance(raw_token, str) or not raw_token:
                raise GraphAuthenticationError(
                    "Microsoft Graph authentication failed."
                )
            expires_in = result.get(
                "expires_in",
                self.config.token_cache_ttl_seconds,
            )
            try:
                lifetime = min(
                    max(60, int(expires_in)),
                    self.config.token_cache_ttl_seconds,
                )
            except (TypeError, ValueError):
                lifetime = self.config.token_cache_ttl_seconds
            token = GraphAccessToken(
                access_token=raw_token,
                expires_at=datetime.now(UTC) + timedelta(seconds=lifetime),
            )
            await self.cache.set(self._cache_key, token)
            return raw_token

    @staticmethod
    def _build_msal_client(config: GraphAuthConfig) -> ConfidentialClient:
        try:
            import msal
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise GraphAuthenticationError(
                "The Microsoft authentication provider is unavailable."
            ) from exc

        authority = (
            "https://login.microsoftonline.com/"
            f"{config.tenant_id.strip()}"
        )
        credential: str | dict[str, str]
        if config.auth_mode == "CLIENT_SECRET":
            assert config.client_secret is not None
            credential = config.client_secret
        else:
            assert config.certificate_path is not None
            credential = {
                "private_key_pfx_path": str(config.certificate_path),
            }
            if config.certificate_password:
                credential["passphrase"] = config.certificate_password
        return msal.ConfidentialClientApplication(
            client_id=config.client_id,
            authority=authority,
            client_credential=credential,
        )
