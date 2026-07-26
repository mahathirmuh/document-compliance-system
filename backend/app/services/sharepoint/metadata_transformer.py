"""Allow-listed SharePoint metadata transformations with no code evaluation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.models.sharepoint_enums import MetadataDataType

RegisteredTransformer = Callable[[Any], Any]


class SharePointMetadataTransformer:
    """Convert mapped values using data types and registered safe transforms."""

    def __init__(
        self,
        registered: dict[str, RegisteredTransformer] | None = None,
    ) -> None:
        self._registered: dict[str, RegisteredTransformer] = {
            "IDENTITY": lambda value: value,
            "TRIM": lambda value: str(value).strip(),
            "UPPERCASE": lambda value: str(value).strip().upper(),
            "LOWERCASE": lambda value: str(value).strip().lower(),
            **{
                data_type.value: (lambda value: value)
                for data_type in MetadataDataType
            },
        }
        for name, transformer in (registered or {}).items():
            normalized = name.strip().upper()
            if not normalized or not callable(transformer):
                raise ValueError("Registered transformer definitions are invalid.")
            self._registered[normalized] = transformer

    def transform(
        self,
        value: Any,
        *,
        data_type: MetadataDataType,
        transformer_code: str | None = None,
    ) -> Any:
        converted = self._convert_type(value, data_type)
        if transformer_code is None:
            return converted
        code = transformer_code.strip().upper()
        transformer = self._registered.get(code)
        if transformer is None:
            raise ValueError(
                f"Unregistered SharePoint metadata transformer: {code!r}."
            )
        return transformer(converted)

    @staticmethod
    def _convert_type(value: Any, data_type: MetadataDataType) -> Any:
        if data_type is MetadataDataType.INTEGER:
            if isinstance(value, bool):
                raise ValueError("Boolean metadata cannot be converted to integer.")
            return int(value)
        if data_type is MetadataDataType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, int) and value in {0, 1}:
                return bool(value)
            normalized = str(value).strip().casefold()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
            raise ValueError("Boolean metadata must use a recognized value.")
        if data_type is MetadataDataType.DATE:
            if isinstance(value, datetime):
                return value.date().isoformat()
            if isinstance(value, date):
                return value.isoformat()
            return date.fromisoformat(str(value).strip()).isoformat()
        if data_type is MetadataDataType.DATETIME:
            if isinstance(value, datetime):
                parsed = value
            else:
                parsed = datetime.fromisoformat(
                    str(value).strip().replace("Z", "+00:00")
                )
            return parsed.isoformat()
        if data_type is MetadataDataType.JSON_STRING:
            return json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        return str(value)
