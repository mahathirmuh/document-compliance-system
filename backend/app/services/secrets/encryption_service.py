"""AES-256-GCM envelope encryption with explicit key-version metadata."""

from __future__ import annotations

import base64
import binascii
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.secrets.base_secret_provider import BaseSecretProvider


class EncryptionError(ValueError):
    """Authenticated encryption failed without exposing ciphertext or keys."""

    code = "ENCRYPTION_FAILED"


class DecryptionError(EncryptionError):
    code = "DECRYPTION_FAILED"


@dataclass(frozen=True, slots=True)
class EncryptedEnvelope:
    algorithm: str
    key_version: str
    nonce: str
    ciphertext: str

    def serialize(self) -> str:
        return json.dumps(
            {
                "algorithm": self.algorithm,
                "keyVersion": self.key_version,
                "nonce": self.nonce,
                "ciphertext": self.ciphertext,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def parse(cls, payload: str) -> EncryptedEnvelope:
        try:
            value: Any = json.loads(payload)
            if not isinstance(value, dict):
                raise TypeError
            envelope = cls(
                algorithm=str(value["algorithm"]),
                key_version=str(value["keyVersion"]),
                nonce=str(value["nonce"]),
                ciphertext=str(value["ciphertext"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DecryptionError("Encrypted envelope is invalid.") from exc
        if envelope.algorithm != "AES-256-GCM":
            raise DecryptionError("Encrypted envelope algorithm is unsupported.")
        return envelope


class AesGcmEncryptionService:
    """Encrypt UTF-8 state with a 32-byte key and authenticated metadata."""

    def __init__(
        self,
        keys: Mapping[str, bytes],
        *,
        active_key_version: str,
    ) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError(
                "The cryptography package is required for AES-GCM."
            ) from exc
        normalized: dict[str, bytes] = {}
        for version, key in keys.items():
            if not version or len(version) > 100 or len(key) != 32:
                raise EncryptionError("Each encryption key must be exactly 32 bytes.")
            normalized[version] = bytes(key)
        if active_key_version not in normalized:
            raise EncryptionError("Active encryption key version is unavailable.")
        self._aesgcm_type = AESGCM
        self._keys = normalized
        self.active_key_version = active_key_version

    @classmethod
    def from_secret_provider(
        cls,
        provider: BaseSecretProvider,
        *,
        active_key_version: str,
        known_key_versions: tuple[str, ...] = (),
    ) -> AesGcmEncryptionService:
        versions = tuple(dict.fromkeys((active_key_version, *known_key_versions)))
        keys: dict[str, bytes] = {}
        for version in versions:
            secret_name = (
                "ENCRYPTION_KEY"
                if version == active_key_version
                else f"ENCRYPTION_KEY_{version.upper().replace('-', '_')}"
            )
            encoded = provider.get_secret(secret_name)
            try:
                keys[version] = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise EncryptionError("Encryption key encoding is invalid.") from exc
        return cls(keys, active_key_version=active_key_version)

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            raise EncryptionError("Only text values can be encrypted.")
        version = self.active_key_version
        nonce = os.urandom(12)
        associated_data = self._associated_data(version)
        ciphertext = self._aesgcm_type(self._keys[version]).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            associated_data,
        )
        return EncryptedEnvelope(
            algorithm="AES-256-GCM",
            key_version=version,
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
        ).serialize()

    def decrypt(self, payload: str) -> str:
        envelope = EncryptedEnvelope.parse(payload)
        key = self._keys.get(envelope.key_version)
        if key is None:
            raise DecryptionError("Encryption key version is unavailable.")
        try:
            nonce = base64.b64decode(envelope.nonce, validate=True)
            ciphertext = base64.b64decode(
                envelope.ciphertext,
                validate=True,
            )
            if len(nonce) != 12:
                raise ValueError
            plaintext = self._aesgcm_type(key).decrypt(
                nonce,
                ciphertext,
                self._associated_data(envelope.key_version),
            )
            return plaintext.decode("utf-8")
        except Exception as exc:
            raise DecryptionError(
                "Encrypted value could not be authenticated."
            ) from exc

    @staticmethod
    def _associated_data(version: str) -> bytes:
        return f"document-compliance:aes-gcm:{version}".encode()
