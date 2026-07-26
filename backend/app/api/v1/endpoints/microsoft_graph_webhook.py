"""Microsoft Graph validation handshake and fast notification ingress."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.sharepoint_webhook import GraphWebhookAcceptedResponse
from app.services.sharepoint.webhook_processing_service import (
    GraphWebhookProcessingService,
)

router = APIRouter(
    prefix="/integrations/microsoft-graph",
    tags=["Microsoft Graph Webhook"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/webhook",
    response_model=None,
)
async def microsoft_graph_webhook(
    session: Session,
    settings: Configuration,
    payload: dict[str, Any] | None = None,
    validation_token: Annotated[
        str | None,
        Query(alias="validationToken", min_length=1, max_length=4096),
    ] = None,
) -> PlainTextResponse | ApiResponse[GraphWebhookAcceptedResponse]:
    if validation_token is not None:
        return PlainTextResponse(
            validation_token,
            media_type="text/plain",
            headers={"Cache-Control": "no-store"},
        )
    result = await GraphWebhookProcessingService(
        session,
        settings,
    ).accept(payload or {})
    return ApiResponse(
        success=True,
        message="Microsoft Graph notifications accepted.",
        data=result,
        errors=None,
    )
