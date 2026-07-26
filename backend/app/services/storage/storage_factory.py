"""Storage-provider construction kept outside document business services."""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.core.config import Settings, get_settings
from app.integrations.microsoft_graph.sharepoint.sharepoint_download_service import (
    SharePointDownloadService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_file_service import (
    SharePointFileService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_folder_service import (
    SharePointFolderService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_upload_service import (
    SharePointUploadService,
)
from app.services.sharepoint.graph_factory import create_graph_client
from app.services.storage.base_storage import BaseStorage
from app.services.storage.hybrid_storage import HybridStorage
from app.services.storage.local_storage import LocalStorage
from app.services.storage.sharepoint_storage_provider import (
    SharePointStorageProvider,
)

_default_storage: BaseStorage | None = None


class StorageFactory:
    """Create configured private storage implementations."""

    @staticmethod
    def create(
        provider: str,
        root: str | Path,
        *,
        remote_storage: BaseStorage | None = None,
    ) -> BaseStorage:
        normalized = provider.strip().lower()
        if normalized == "local":
            return LocalStorage(root)
        if normalized == "sharepoint" and remote_storage is not None:
            return remote_storage
        if normalized == "hybrid" and remote_storage is not None:
            return HybridStorage(
                local=LocalStorage(root),
                remote=remote_storage,
            )
        raise ValueError(f"Unsupported storage provider: {provider!r}.")

    @classmethod
    def get_storage(
        cls,
        settings: Settings | None = None,
    ) -> BaseStorage:
        resolved_settings = settings or get_settings()
        remote_storage = (
            cls._sharepoint_storage(resolved_settings)
            if resolved_settings.storage_provider in {"sharepoint", "hybrid"}
            else None
        )
        return cls.create(
            resolved_settings.storage_provider,
            resolved_settings.storage_root,
            remote_storage=remote_storage,
        )

    @staticmethod
    def _sharepoint_storage(settings: Settings) -> BaseStorage:
        if not settings.sharepoint_drive_id:
            raise ValueError("SHAREPOINT_DRIVE_ID is required for SharePoint storage.")
        client = create_graph_client(settings)
        uploads = SharePointUploadService(
            client,
            simple_upload_max_bytes=(
                settings.sharepoint_simple_upload_max_mb * 1024 * 1024
            ),
            chunk_size_bytes=(settings.sharepoint_upload_chunk_size_mb * 1024 * 1024),
            maximum_file_size_bytes=(
                settings.sharepoint_upload_max_file_size_mb * 1024 * 1024
            ),
        )
        connection_id = uuid5(
            NAMESPACE_URL,
            (
                "document-compliance-sharepoint:"
                f"{settings.microsoft_tenant_id}:{settings.sharepoint_drive_id}"
            ),
        )
        return SharePointStorageProvider(
            connection_id=connection_id,
            drive_id=settings.sharepoint_drive_id,
            root_folder_path=settings.sharepoint_root_folder_path,
            uploads=uploads,
            downloads=SharePointDownloadService(
                client,
                chunk_size=settings.file_download_chunk_size_kb * 1024,
            ),
            files=SharePointFileService(client),
            folders=SharePointFolderService(client),
        )


def get_storage(settings: Settings | None = None) -> BaseStorage:
    """Dependency-friendly module-level factory."""
    global _default_storage
    if settings is not None:
        return StorageFactory.get_storage(settings)
    if _default_storage is None:
        _default_storage = StorageFactory.get_storage()
    return _default_storage


async def close_default_storage() -> None:
    """Close the cached provider without creating it during shutdown."""

    global _default_storage
    if _default_storage is not None:
        await _default_storage.close()
        _default_storage = None
