"""Secret-safe Graph webhook validation and payload deduplication helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


class SharePointWebhookService:
    @staticmethod
    def client_state_hash(client_state: str) -> str:
        if not client_state:
            raise ValueError("Webhook client state must not be empty.")
        return hashlib.sha256(client_state.encode("utf-8")).hexdigest()

    @classmethod
    def validate_client_state(
        cls,
        supplied: str | None,
        stored_hash: str,
    ) -> bool:
        if not supplied:
            return False
        candidate = cls.client_state_hash(supplied)
        return hmac.compare_digest(candidate, stored_hash)

    @staticmethod
    def payload_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_notifications(
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        values = payload.get("value")
        if not isinstance(values, list):
            raise TypeError("Webhook payload must contain a value array.")
        return [item for item in values if isinstance(item, dict)]

    @staticmethod
    def safe_metadata(notification: dict[str, Any]) -> dict[str, Any]:
        resource_data = notification.get("resourceData")
        resource_id = (
            resource_data.get("id")
            if isinstance(resource_data, dict)
            else None
        )
        return {
            "subscriptionId": notification.get("subscriptionId"),
            "changeType": notification.get("changeType"),
            "resourceId": resource_id,
        }
