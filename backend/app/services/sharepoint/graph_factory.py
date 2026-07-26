"""Compose Graph and SharePoint adapters from validated application settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.microsoft_graph.graph_auth_provider import (
    GraphAuthConfig,
    MsalGraphAuthProvider,
)
from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_rate_limit_service import (
    GraphRateLimitService,
)
from app.integrations.microsoft_graph.graph_request_service import (
    GraphRequestService,
)
from app.integrations.microsoft_graph.graph_retry_policy import (
    GraphRetryPolicy,
)


def _secret_value(value: Any) -> str | None:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, str):
        return value
    return None


def create_graph_client(
    settings: Settings,
    *,
    http_client: Any = None,
) -> GraphClient:
    if not bool(getattr(settings, "microsoft_graph_enabled", False)):
        raise RuntimeError("SHAREPOINT_DISABLED")
    tenant_id = str(getattr(settings, "microsoft_tenant_id", "") or "")
    client_id = str(getattr(settings, "microsoft_client_id", "") or "")
    auth_mode = str(
        getattr(settings, "microsoft_graph_auth_mode", "client_secret")
    ).upper()
    config = GraphAuthConfig(
        tenant_id=tenant_id,
        client_id=client_id,
        auth_mode=auth_mode,
        client_secret=_secret_value(
            getattr(settings, "microsoft_client_secret", None)
        ),
        certificate_path=(
            Path(value)
            if (
                value := getattr(
                    settings,
                    "microsoft_client_certificate_path",
                    None,
                )
            )
            else None
        ),
        certificate_password=_secret_value(
            getattr(
                settings,
                "microsoft_client_certificate_password",
                None,
            )
        ),
        token_cache_ttl_seconds=int(
            getattr(
                settings,
                "microsoft_graph_token_cache_ttl_seconds",
                3000,
            )
        ),
    )
    retry = GraphRetryPolicy(
        maximum_retries=int(
            getattr(settings, "microsoft_graph_max_retries", 5)
        ),
        base_seconds=float(
            getattr(settings, "microsoft_graph_retry_base_seconds", 2)
        ),
        maximum_seconds=float(
            getattr(settings, "microsoft_graph_retry_max_seconds", 120)
        ),
    )
    requests = GraphRequestService(
        auth_provider=MsalGraphAuthProvider(config),
        base_url=str(
            getattr(
                settings,
                "microsoft_graph_base_url",
                "https://graph.microsoft.com/v1.0",
            )
        ),
        timeout_seconds=float(
            getattr(settings, "microsoft_graph_timeout_seconds", 60)
        ),
        retry_policy=retry,
        rate_limits=GraphRateLimitService(
            maximum_concurrency=int(
                getattr(settings, "sharepoint_worker_concurrency", 4)
            )
        ),
        http_client=http_client,
    )
    return GraphClient(requests)
