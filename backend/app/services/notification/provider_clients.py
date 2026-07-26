"""Concrete outbound provider clients with bounded, secret-safe failures."""

from __future__ import annotations

import re
from typing import Any

import httpx

_TELEGRAM_TOKEN = re.compile(r"^[0-9]{5,20}:[A-Za-z0-9_-]{20,100}$")


class HttpTeamsWebhookClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.transport = transport

    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> str | None:
        async with httpx.AsyncClient(
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            response = await client.post(
                url,
                json=payload,
                timeout=timeout_seconds,
            )
        if not 200 <= response.status_code < 300:
            raise RuntimeError("Microsoft Teams rejected the notification.")
        provider_id = response.headers.get("request-id") or response.headers.get(
            "x-ms-request-id"
        )
        return provider_id[:1000] if provider_id else None


class HttpTelegramBotClient:
    def __init__(
        self,
        *,
        bot_token: str,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._bot_token = bot_token.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
    ) -> str | None:
        if not _TELEGRAM_TOKEN.fullmatch(self._bot_token):
            raise RuntimeError("Telegram bot authentication is not configured.")
        async with httpx.AsyncClient(
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            response = await client.post(
                (f"https://api.telegram.org/bot{self._bot_token}/sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout_seconds,
            )
        if response.status_code != 200:
            raise RuntimeError("Telegram rejected the notification.")
        try:
            value = response.json()
            message_id = value["result"]["message_id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                "Telegram returned an invalid notification response."
            ) from exc
        return str(message_id)[:1000]
