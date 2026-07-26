"""Controlled SharePoint list-column mapping and transformers."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)

Transformer = Callable[[Any], Any]


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError("Value cannot be transformed to boolean.")


class SharePointMetadataService:
    """Only allow explicitly registered transformations; never eval config."""

    def __init__(
        self,
        client: GraphClient,
        *,
        custom_transformers: dict[str, Transformer] | None = None,
    ) -> None:
        self.client = client
        self.transformers: dict[str, Transformer] = {
            "STRING": lambda value: str(value),
            "INTEGER": lambda value: int(value),
            "BOOLEAN": _boolean,
            "DATE": self._date,
            "DATETIME": self._datetime,
            "CHOICE": lambda value: str(value),
            "LOOKUP_TEXT": lambda value: str(value),
            "USER_DISPLAY_NAME": lambda value: str(value),
            "JSON_STRING": lambda value: json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        for code, transformer in (custom_transformers or {}).items():
            normalized = code.strip().upper()
            if not normalized or normalized in self.transformers:
                raise ValueError("Custom transformer code is invalid or duplicate.")
            self.transformers[normalized] = transformer

    def transform(self, code: str, value: Any) -> Any:
        normalized = code.strip().upper()
        transformer = self.transformers.get(normalized)
        if transformer is None:
            raise ValueError("Metadata transformer is not registered.")
        if value is None:
            return None
        return transformer(value)

    async def update_fields(
        self,
        *,
        drive_id: str,
        item_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        if not fields or any(
            not key.strip() or " " in key for key in fields
        ):
            raise ValueError(
                "SharePoint metadata requires internal field names."
            )
        return await self.client.patch(
            f"/drives/{encode_identifier(drive_id)}/items/"
            f"{encode_identifier(item_id)}/listItem/fields",
            payload=fields,
        )

    @staticmethod
    def _date(value: Any) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return date.fromisoformat(str(value)).isoformat()

    @staticmethod
    def _datetime(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
