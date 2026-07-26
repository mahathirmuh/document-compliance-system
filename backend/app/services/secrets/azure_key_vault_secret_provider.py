"""Optional Azure Key Vault adapter with dependency injection."""

from __future__ import annotations

import re
from typing import Protocol

from app.services.secrets.base_secret_provider import (
    BaseSecretProvider,
    SecretNotFoundError,
    SecretProviderError,
)

_VALID_KEY_VAULT_NAME = re.compile(r"^[A-Za-z0-9-]{1,127}$")


class KeyVaultSecret(Protocol):
    value: str | None


class KeyVaultClient(Protocol):
    def get_secret(self, name: str) -> KeyVaultSecret: ...


class AzureKeyVaultSecretProvider(BaseSecretProvider):
    """Wrap an already-authenticated Azure client without importing its SDK."""

    def __init__(
        self,
        client: KeyVaultClient,
        *,
        name_prefix: str = "",
    ) -> None:
        self.client = client
        self.name_prefix = name_prefix.strip("-")

    def get_secret(self, name: str) -> str:
        vault_name = name.casefold().replace("_", "-")
        if self.name_prefix:
            vault_name = f"{self.name_prefix}-{vault_name}"
        if not _VALID_KEY_VAULT_NAME.fullmatch(vault_name):
            raise SecretNotFoundError("Secret name is invalid.")
        try:
            secret = self.client.get_secret(vault_name)
        except Exception as exc:
            raise SecretProviderError("Azure Key Vault is unavailable.") from exc
        if not secret.value:
            raise SecretNotFoundError("Secret is not configured.")
        return secret.value
