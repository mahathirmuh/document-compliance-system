"""Focused tests for provider-neutral, root-enforced local storage."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.storage.file_stream_service import (
    FileStreamService,
    StreamLimitExceededError,
)
from app.services.storage.local_storage import (
    LocalStorage,
    UnsafeStorageKeyError,
)
from app.services.storage.storage_factory import StorageFactory
from app.services.storage.storage_path_service import (
    StoragePathService,
    UnsafeFilenameError,
    sanitize_filename,
)


@pytest.mark.asyncio
async def test_local_storage_save_open_move_delete_is_streamed_and_idempotent(
    tmp_path,
) -> None:
    storage = LocalStorage(tmp_path, copy_chunk_size=3)
    payload = b"physical-document-content"

    result = await storage.save(
        io.BytesIO(payload),
        "documents/temporary/session/file.pdf",
    )

    assert result == {
        "storage_key": "documents/temporary/session/file.pdf",
        "storage_provider": "local",
        "size": len(payload),
    }
    assert await storage.exists(result["storage_key"])
    assert await storage.get_size(result["storage_key"]) == len(payload)
    source = await storage.open(result["storage_key"])
    try:
        assert source.read() == payload
    finally:
        source.close()

    destination = "documents/originals/2026/07/doc/rev/file.pdf"
    await storage.move(result["storage_key"], destination)
    assert not await storage.exists(result["storage_key"])
    assert await storage.exists(destination)
    await storage.delete(destination)
    await storage.delete(destination)
    assert not await storage.exists(destination)


@pytest.mark.asyncio
async def test_local_storage_never_overwrites_objects(tmp_path) -> None:
    storage = LocalStorage(tmp_path)
    key = "documents/temporary/file.pdf"
    await storage.save(io.BytesIO(b"first"), key)

    with pytest.raises(FileExistsError):
        await storage.save(io.BytesIO(b"second"), key)

    source = await storage.open(key)
    try:
        assert source.read() == b"first"
    finally:
        source.close()


@pytest.mark.asyncio
async def test_local_storage_supports_required_long_original_key(
    tmp_path,
) -> None:
    storage = LocalStorage(tmp_path)
    source_key = "documents/temporary/session/file.pdf"
    destination_key = (
        "documents/originals/2026/07/"
        "00000000-0000-0000-0000-000000000001/"
        "00000000-0000-0000-0000-000000000002/"
        "00000000-0000-0000-0000-000000000003_"
        f"{'A' * 140}.pdf"
    )
    assert len(str(storage.resolve_key(destination_key))) > 260
    await storage.save(io.BytesIO(b"long-path-content"), source_key)

    await storage.move(source_key, destination_key)

    assert await storage.exists(destination_key)
    assert await storage.get_size(destination_key) == 17
    source = await storage.open(destination_key)
    try:
        assert source.read() == b"long-path-content"
    finally:
        source.close()
    await storage.delete(destination_key)
    assert not await storage.exists(destination_key)


@pytest.mark.parametrize(
    "storage_key",
    [
        "../secret.pdf",
        "documents/../../secret.pdf",
        "/var/data/file.pdf",
        r"documents\temporary\file.pdf",
        r"C:\Windows\file.pdf",
        "documents/./file.pdf",
        "",
    ],
)
def test_local_storage_rejects_path_traversal(
    tmp_path,
    storage_key: str,
) -> None:
    storage = LocalStorage(tmp_path)
    with pytest.raises(UnsafeStorageKeyError):
        storage.resolve_key(storage_key)


@pytest.mark.asyncio
async def test_bounded_stream_removes_partial_object_on_overflow(
    tmp_path,
) -> None:
    storage = LocalStorage(tmp_path, copy_chunk_size=2)
    key = "documents/temporary/oversized.pdf"

    with pytest.raises(StreamLimitExceededError):
        await FileStreamService.save_with_limit(
            storage,
            io.BytesIO(b"123456"),
            key,
            max_bytes=5,
        )

    assert not await storage.exists(key)


@pytest.mark.asyncio
async def test_download_iterator_reads_bounded_chunks(tmp_path) -> None:
    storage = LocalStorage(tmp_path)
    key = "documents/originals/file.pdf"
    await storage.save(io.BytesIO(b"abcdefgh"), key)

    chunks = [
        chunk
        async for chunk in FileStreamService.iter_storage(
            storage,
            key,
            chunk_size=3,
        )
    ]

    assert chunks == [b"abc", b"def", b"gh"]


def test_filename_sanitization_and_path_generation() -> None:
    assert (
        sanitize_filename("Résumé policy (final).PDF")
        == "Resume_policy_final.pdf"
    )
    with pytest.raises(UnsafeFilenameError):
        sanitize_filename("../../secret.pdf")
    with pytest.raises(UnsafeFilenameError):
        sanitize_filename(r"C:\Windows\secret.pdf")

    settings = Settings(
        database_url=(
            "postgresql+asyncpg://user:password@localhost:5432/app"
        ),
    )
    paths = StoragePathService(settings)
    document_id = UUID("00000000-0000-0000-0000-000000000001")
    revision_id = UUID("00000000-0000-0000-0000-000000000002")
    file_id = UUID("00000000-0000-0000-0000-000000000003")
    at = datetime(2026, 7, 25, tzinfo=UTC)

    assert paths.original_key(
        document_id,
        revision_id,
        file_id,
        "Policy Final.pdf",
        at=at,
    ) == (
        "documents/originals/2026/07/"
        "00000000-0000-0000-0000-000000000001/"
        "00000000-0000-0000-0000-000000000002/"
        "00000000-0000-0000-0000-000000000003_Policy_Final.pdf"
    )


def test_storage_factory_supports_only_configured_local_provider(
    tmp_path,
) -> None:
    assert isinstance(StorageFactory.create("local", tmp_path), LocalStorage)
    with pytest.raises(ValueError, match="Unsupported storage provider"):
        StorageFactory.create("public-filesystem", tmp_path)


def test_phase5_storage_settings_are_validated() -> None:
    common = {
        "database_url": (
            "postgresql+asyncpg://user:password@localhost:5432/app"
        )
    }
    settings = Settings(
        **common,
        allowed_document_extensions="PDF,.docx,xlsx",
        document_max_file_size_mb=50,
        document_batch_max_total_size_mb=500,
    )
    assert settings.allowed_document_extension_set == {
        ".pdf",
        ".docx",
        ".xlsx",
    }
    assert settings.document_max_file_size_bytes == 50 * 1024 * 1024
    assert (
        settings.document_batch_max_total_size_bytes
        == 500 * 1024 * 1024
    )

    with pytest.raises(ValidationError, match="Storage prefixes"):
        Settings(**common, storage_temp_prefix="../temporary")
    with pytest.raises(ValidationError, match="only .pdf"):
        Settings(
            **common,
            allowed_document_extensions=".pdf,.pptx",
        )
