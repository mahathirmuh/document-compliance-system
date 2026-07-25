"""Streaming SHA-256 helpers for physical document files."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import BinaryIO

DEFAULT_HASH_CHUNK_SIZE = 1024 * 1024


def calculate_stream_sha256(
    source: BinaryIO,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE,
) -> str:
    """Hash a seekable binary stream without retaining file content."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    try:
        original_position = source.tell()
        source.seek(0)
    except (AttributeError, OSError) as exc:
        raise ValueError("SHA-256 source must be seekable.") from exc

    digest = hashlib.sha256()
    try:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    finally:
        source.seek(original_position)
    return digest.hexdigest()


def calculate_sha256(
    file_path: str | Path,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE,
) -> str:
    """Hash a file path in bounded chunks."""
    path = Path(file_path)
    with path.open("rb") as source:
        return calculate_stream_sha256(source, chunk_size)


async def calculate_sha256_async(
    file_path: str | Path,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE,
) -> str:
    """Run filesystem hashing outside the event loop."""
    return await asyncio.to_thread(calculate_sha256, file_path, chunk_size)


async def calculate_stream_sha256_async(
    source: BinaryIO,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE,
) -> str:
    """Run seekable-stream hashing outside the event loop."""
    return await asyncio.to_thread(
        calculate_stream_sha256,
        source,
        chunk_size,
    )


class FileHashService:
    """Injectable façade used by upload services."""

    calculate_sha256 = staticmethod(calculate_sha256)
    calculate_sha256_async = staticmethod(calculate_sha256_async)
    calculate_stream_sha256 = staticmethod(calculate_stream_sha256)
    calculate_stream_sha256_async = staticmethod(
        calculate_stream_sha256_async
    )
