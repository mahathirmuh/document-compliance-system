"""Backward-compatible facade for allow-listed SharePoint transformations."""

from __future__ import annotations

from typing import Any, cast

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.sharepoint.sharepoint_metadata_service import (
    SharePointMetadataService,
    Transformer,
)
from app.models.sharepoint_enums import MetadataDataType


class SharePointMetadataTransformer:
    """Preserve the typed service contract while sharing one safe registry."""

    def __init__(
        self,
        registered: dict[str, Transformer] | None = None,
    ) -> None:
        self._service = SharePointMetadataService(
            cast(GraphClient, None),
            custom_transformers=registered,
        )

    def transform(
        self,
        value: Any,
        *,
        data_type: MetadataDataType,
        transformer_code: str | None = None,
    ) -> Any:
        converted = self._service.transform(data_type.value, value)
        if transformer_code is None:
            return converted
        return self._service.transform(transformer_code, converted)
