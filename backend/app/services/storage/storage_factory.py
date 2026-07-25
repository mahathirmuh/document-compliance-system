"""Storage-provider construction kept outside document business services."""

from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.storage.base_storage import BaseStorage
from app.services.storage.local_storage import LocalStorage


class StorageFactory:
    """Create configured private storage implementations."""

    @staticmethod
    def create(
        provider: str,
        root: str | Path,
    ) -> BaseStorage:
        normalized = provider.strip().lower()
        if normalized == "local":
            return LocalStorage(root)
        raise ValueError(f"Unsupported storage provider: {provider!r}.")

    @classmethod
    def get_storage(
        cls,
        settings: Settings | None = None,
    ) -> BaseStorage:
        resolved_settings = settings or get_settings()
        return cls.create(
            resolved_settings.storage_provider,
            resolved_settings.storage_root,
        )


def get_storage(settings: Settings | None = None) -> BaseStorage:
    """Dependency-friendly module-level factory."""
    return StorageFactory.get_storage(settings)
