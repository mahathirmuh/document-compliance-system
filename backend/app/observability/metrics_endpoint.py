"""Factory for a network-protected Prometheus scrape endpoint."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from app.observability.metrics import MetricsRegistry


def create_metrics_router(
    registry: MetricsRegistry,
    *,
    access_token: str | None = None,
) -> APIRouter:
    """Create `/metrics`; prefer network policy and optionally require a token."""

    router = APIRouter(tags=["Observability"])

    @router.get(
        "/metrics",
        response_class=PlainTextResponse,
        include_in_schema=False,
    )
    async def metrics(
        supplied_token: Annotated[
            str | None,
            Header(alias="X-Metrics-Token"),
        ] = None,
    ) -> PlainTextResponse:
        if access_token is not None and (
            supplied_token is None
            or not secrets.compare_digest(supplied_token, access_token)
        ):
            raise HTTPException(status_code=404, detail="Not found.")
        return PlainTextResponse(
            await registry.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return router
