"""Bounded Microsoft Graph ``sendMail`` operation with no token exposure."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import quote

from app.core.config import Settings
from app.integrations.microsoft_graph.graph_client import GraphClient
from app.services.sharepoint.graph_factory import create_graph_client


class GraphClientFactory(Protocol):
    def __call__(self, settings: Settings) -> GraphClient: ...


class GraphMailService:
    """Create one short-lived Graph client for each worker mail operation."""

    def __init__(
        self,
        settings: Settings,
        *,
        graph_factory: GraphClientFactory = create_graph_client,
    ) -> None:
        self.settings = settings
        self.graph_factory = graph_factory

    async def send_mail(
        self,
        *,
        sender_user_id: str,
        message: dict[str, Any],
        client_request_id: str | None,
    ) -> str | None:
        sender = sender_user_id.strip()
        if not sender or len(sender) > 320:
            raise ValueError("The configured Graph sender is invalid.")
        self._validate_message(message)
        graph = self.graph_factory(self.settings)
        try:
            await graph.post(
                f"/users/{quote(sender, safe='')}/sendMail",
                payload={
                    "message": message,
                    "saveToSentItems": True,
                },
                expected_statuses={202},
            )
        finally:
            await graph.close()
        # Graph sendMail returns 202 without a message resource identifier.
        # The bounded correlation ID is sufficient for internal delivery history.
        return client_request_id[:128] if client_request_id else None

    @staticmethod
    def _validate_message(message: Mapping[str, Any]) -> None:
        subject = message.get("subject")
        body = message.get("body")
        recipients = message.get("toRecipients")
        if (
            not isinstance(subject, str)
            or len(subject) > 500
            or not isinstance(body, Mapping)
            or not isinstance(body.get("content"), str)
            or len(str(body["content"])) > 100_000
            or not isinstance(recipients, list)
            or not 1 <= len(recipients) <= 500
        ):
            raise ValueError("The Graph mail message is outside safe bounds.")
