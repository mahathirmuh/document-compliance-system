"""Base protocol and safe channel failure types."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.notification_enums import NotificationChannel
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationMessage,
)


class NotificationChannelError(Exception):
    """Provider failure safe to persist without credentials or payload text."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:1000]
        self.retryable = retryable


class BaseNotificationChannel(ABC):
    channel: NotificationChannel

    @abstractmethod
    async def send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> DeliveryResult:
        """Send a bounded message without leaking provider credentials."""
