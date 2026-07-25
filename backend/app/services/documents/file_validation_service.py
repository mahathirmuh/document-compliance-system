"""Streaming physical-file validation for the Phase 5 upload pipeline."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import BinaryIO

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.schemas.common import ErrorDetail
from app.services.documents.file_hash_service import (
    calculate_stream_sha256,
)
from app.services.documents.file_signature_service import (
    FileSignatureError,
    FileSignatureService,
)
from app.services.storage.base_storage import BaseStorage
from app.services.storage.storage_path_service import (
    UnsafeFilenameError,
    sanitize_filename,
)

MIME_TYPES_BY_EXTENSION = {
    "pdf": "application/pdf",
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
}
SPOOL_MEMORY_LIMIT = 8 * 1024 * 1024
STREAM_COPY_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileValidationResult:
    sanitized_filename: str
    extension: str
    declared_mime_type: str
    detected_mime_type: str
    file_size: int
    sha256_hash: str

    @property
    def file_extension(self) -> str:
        """Compatibility alias for persistence/schema field names."""
        return self.extension

    @property
    def mime_type(self) -> str:
        return self.declared_mime_type


def _validation_error(
    message: str,
    *,
    status_code: int,
    field: str | None = "file",
) -> ApplicationError:
    return ApplicationError(
        "File validation failed.",
        status_code=status_code,
        errors=[ErrorDetail(field=field, message=message)],
    )


class FileValidationService:
    """Validate filename, size, MIME, signature, and hash consistently."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.signature_service = FileSignatureService(
            max_entries=self.settings.ooxml_max_entries,
            max_uncompressed_size=(
                self.settings.ooxml_max_uncompressed_size_bytes
            ),
            max_compression_ratio=(
                self.settings.ooxml_max_compression_ratio
            ),
        )

    def validate_upload_metadata(
        self,
        original_filename: str,
        declared_mime_type: str,
    ) -> tuple[str, str, str]:
        """Validate request metadata before touching persistent storage."""
        try:
            sanitized = sanitize_filename(original_filename)
        except UnsafeFilenameError as exc:
            raise _validation_error(
                str(exc),
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                field="filename",
            ) from exc

        extension_with_dot = Path(sanitized).suffix.lower()
        if extension_with_dot not in (
            self.settings.allowed_document_extension_set
        ):
            raise _validation_error(
                "Only PDF, DOCX, and XLSX files are supported.",
                status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                field="filename",
            )
        extension = extension_with_dot.lstrip(".")

        declared = declared_mime_type.split(";", 1)[0].strip().lower()
        expected_mime = MIME_TYPES_BY_EXTENSION[extension]
        if declared != expected_mime:
            raise _validation_error(
                "Declared MIME type does not match the file extension.",
                status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                field="contentType",
            )
        return sanitized, extension, declared

    def validate_request_size(
        self,
        file_size: int,
        *,
        max_size_bytes: int | None = None,
    ) -> None:
        limit = self._effective_limit(max_size_bytes)
        if file_size < 0:
            raise _validation_error(
                "File size cannot be negative.",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        if file_size > limit:
            raise _validation_error(
                "File exceeds the configured maximum size.",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

    async def validate_storage(
        self,
        storage: BaseStorage,
        storage_key: str,
        *,
        original_filename: str,
        declared_mime_type: str,
        max_size_bytes: int | None = None,
    ) -> FileValidationResult:
        """Validate a provider object without exposing its physical path."""
        size = await storage.get_size(storage_key)
        self.validate_request_size(
            size,
            max_size_bytes=max_size_bytes,
        )
        source = await storage.open(storage_key)
        try:
            return await self.validate_stream(
                source,
                original_filename=original_filename,
                declared_mime_type=declared_mime_type,
                max_size_bytes=max_size_bytes,
            )
        finally:
            await asyncio.to_thread(source.close)

    async def validate_stream(
        self,
        source: BinaryIO,
        *,
        original_filename: str,
        declared_mime_type: str,
        max_size_bytes: int | None = None,
    ) -> FileValidationResult:
        """Validate a binary stream using bounded disk spooling if needed."""
        sanitized, extension, declared = self.validate_upload_metadata(
            original_filename,
            declared_mime_type,
        )
        limit = self._effective_limit(max_size_bytes)
        return await asyncio.to_thread(
            self._validate_stream_sync,
            source,
            sanitized,
            extension,
            declared,
            limit,
        )

    async def validate_stored_file(
        self,
        path: str | Path,
        original_filename: str,
        declared_mime_type: str,
        max_size_bytes: int | None = None,
    ) -> FileValidationResult:
        """Compatibility path entrypoint for infrastructure-level tests."""
        source = await asyncio.to_thread(Path(path).open, "rb")
        try:
            return await self.validate_stream(
                source,
                original_filename=original_filename,
                declared_mime_type=declared_mime_type,
                max_size_bytes=max_size_bytes,
            )
        finally:
            await asyncio.to_thread(source.close)

    async def validate_file(
        self,
        path: str | Path,
        original_filename: str,
        declared_mime_type: str,
        max_size_bytes: int | None = None,
    ) -> FileValidationResult:
        return await self.validate_stored_file(
            path,
            original_filename,
            declared_mime_type,
            max_size_bytes,
        )

    def _validate_stream_sync(
        self,
        source: BinaryIO,
        sanitized_filename: str,
        extension: str,
        declared_mime_type: str,
        max_size_bytes: int,
    ) -> FileValidationResult:
        stream, should_close = self._seekable_stream(
            source,
            max_size_bytes,
        )
        try:
            file_size = self._stream_size(stream)
            self.validate_request_size(
                file_size,
                max_size_bytes=max_size_bytes,
            )
            detected_extension = extension
            if self.settings.enable_file_signature_validation:
                try:
                    detected_extension = (
                        self.signature_service.detect_file_type(stream)
                    )
                except FileSignatureError as exc:
                    raise _validation_error(
                        str(exc),
                        status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    ) from exc
                if detected_extension != extension:
                    raise _validation_error(
                        "File extension, MIME type, and signature do not "
                        "match.",
                        status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    )

            sha256_hash = calculate_stream_sha256(stream)
            return FileValidationResult(
                sanitized_filename=sanitized_filename,
                extension=extension,
                declared_mime_type=declared_mime_type,
                detected_mime_type=MIME_TYPES_BY_EXTENSION[
                    detected_extension
                ],
                file_size=file_size,
                sha256_hash=sha256_hash,
            )
        finally:
            if should_close:
                stream.close()

    @staticmethod
    def _stream_size(source: BinaryIO) -> int:
        original_position = source.tell()
        source.seek(0, 2)
        size = source.tell()
        source.seek(original_position)
        return size

    @staticmethod
    def _seekable_stream(
        source: BinaryIO,
        max_size_bytes: int,
    ) -> tuple[BinaryIO, bool]:
        try:
            if source.seekable():
                return source, False
        except (AttributeError, OSError):
            pass

        spool = tempfile.SpooledTemporaryFile(  # noqa: SIM115
            max_size=min(SPOOL_MEMORY_LIMIT, max_size_bytes)
        )
        total = 0
        try:
            while chunk := source.read(STREAM_COPY_CHUNK_SIZE):
                total += len(chunk)
                if total > max_size_bytes:
                    raise _validation_error(
                        "File exceeds the configured maximum size.",
                        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    )
                spool.write(chunk)
            spool.seek(0)
            return spool, True
        except Exception:
            spool.close()
            raise

    def _effective_limit(self, max_size_bytes: int | None) -> int:
        configured = self.settings.document_max_file_size_bytes
        if max_size_bytes is None:
            return configured
        if max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be positive.")
        return min(configured, max_size_bytes)
