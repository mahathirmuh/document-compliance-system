"""Provider-neutral secret access contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretProviderError(RuntimeError):
    """Secret lookup failure without exposing names' values."""

    code = "SECRET_PROVIDER_UNAVAILABLE"


class SecretNotFoundError(SecretProviderError):
    code = "SECRET_NOT_FOUND"


class BaseSecretProvider(ABC):
    @abstractmethod
    def get_secret(self, name: str) -> str:
        """Return a secret value; callers must never log the result."""
