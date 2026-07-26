"""Minimal Phase 10 environment-backed secret provider."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from app.services.secrets.base_secret_provider import (
    BaseSecretProvider,
    SecretNotFoundError,
)

_VALID_SECRET_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")


class EnvironmentSecretProvider(BaseSecretProvider):
    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self._environment = environment if environment is not None else os.environ

    def get_secret(self, name: str) -> str:
        if not _VALID_SECRET_NAME.fullmatch(name):
            raise SecretNotFoundError("Secret name is invalid.")
        value = self._environment.get(name)
        if value is None or not value:
            raise SecretNotFoundError(f"Required secret '{name}' is not configured.")
        return value
