"""Transactionally rotate encrypted integration state without printing secrets."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import json
from dataclasses import dataclass

from sqlalchemy import select

from app.database.session import AsyncSessionFactory
from app.models.sharepoint_delta_state import SharePointDeltaState
from app.services.secrets.encryption_service import (
    AesGcmEncryptionService,
    EncryptedEnvelope,
    EncryptionError,
)
from app.services.secrets.environment_secret_provider import (
    EnvironmentSecretProvider,
)


@dataclass(frozen=True, slots=True)
class RotationArguments:
    old_key_environment_name: str
    old_key_version: str
    new_key_environment_name: str
    new_key_version: str
    dry_run: bool
    batch_size: int


def _arguments() -> RotationArguments:
    parser = argparse.ArgumentParser(
        description="Rotate AES-GCM SharePoint delta-state envelopes.",
    )
    parser.add_argument(
        "--old-key-env",
        default="ENCRYPTION_KEY_OLD",
        help="Environment variable containing the old base64 32-byte key.",
    )
    parser.add_argument("--old-key-version", required=True)
    parser.add_argument(
        "--new-key-env",
        default="ENCRYPTION_KEY",
        help="Environment variable containing the new base64 32-byte key.",
    )
    parser.add_argument("--new-key-version", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parsed = parser.parse_args()
    if not 1 <= parsed.batch_size <= 5000:
        parser.error("--batch-size must be between 1 and 5000.")
    if parsed.old_key_version == parsed.new_key_version:
        parser.error("Old and new key versions must differ.")
    return RotationArguments(
        old_key_environment_name=parsed.old_key_env,
        old_key_version=parsed.old_key_version,
        new_key_environment_name=parsed.new_key_env,
        new_key_version=parsed.new_key_version,
        dry_run=parsed.dry_run,
        batch_size=parsed.batch_size,
    )


def _key(provider: EnvironmentSecretProvider, name: str) -> bytes:
    try:
        key = base64.b64decode(provider.get_secret(name), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EncryptionError("Encryption key encoding is invalid.") from exc
    if len(key) != 32:
        raise EncryptionError("Encryption key must be exactly 32 bytes.")
    return key


async def rotate(arguments: RotationArguments) -> dict[str, int | bool]:
    provider = EnvironmentSecretProvider()
    old_cipher = AesGcmEncryptionService(
        {
            arguments.old_key_version: _key(
                provider,
                arguments.old_key_environment_name,
            )
        },
        active_key_version=arguments.old_key_version,
    )
    new_cipher = AesGcmEncryptionService(
        {
            arguments.new_key_version: _key(
                provider,
                arguments.new_key_environment_name,
            )
        },
        active_key_version=arguments.new_key_version,
    )
    scanned = rotated = already_current = failed = 0
    last_id = None
    async with AsyncSessionFactory() as session:  # noqa: SIM117
        async with session.begin():
            while True:
                statement = (
                    select(SharePointDeltaState)
                    .order_by(SharePointDeltaState.id.asc())
                    .limit(arguments.batch_size)
                )
                if last_id is not None:
                    statement = statement.where(SharePointDeltaState.id > last_id)
                rows = list(await session.scalars(statement))
                if not rows:
                    break
                for row in rows:
                    scanned += 1
                    last_id = row.id
                    try:
                        envelope = EncryptedEnvelope.parse(row.delta_link_encrypted)
                        if envelope.key_version == arguments.new_key_version:
                            already_current += 1
                            continue
                        if envelope.key_version != arguments.old_key_version:
                            raise EncryptionError(
                                "Encrypted value uses an unexpected key version."
                            )
                        plaintext = old_cipher.decrypt(row.delta_link_encrypted)
                    except EncryptionError:
                        failed += 1
                        continue
                    if not arguments.dry_run:
                        row.delta_link_encrypted = new_cipher.encrypt(plaintext)
                    rotated += 1
            if failed:
                raise EncryptionError(
                    "Rotation aborted because one or more values could not "
                    "be authenticated."
                )
    return {
        "dryRun": arguments.dry_run,
        "scanned": scanned,
        "rotated": rotated,
        "alreadyCurrent": already_current,
        "failed": failed,
    }


def main() -> None:
    summary = asyncio.run(rotate(_arguments()))
    print(json.dumps(summary, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
