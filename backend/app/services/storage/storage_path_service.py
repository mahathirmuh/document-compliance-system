"""Safe storage-key and filename generation for physical documents."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID

from app.core.config import Settings, get_settings

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_UNDERSCORE = re.compile(r"_+")
_WINDOWS_RESERVED_NAMES = {
    "AUX",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "CON",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
    "NUL",
    "PRN",
}


class UnsafeFilenameError(ValueError):
    """A client filename contains path or control semantics."""


def sanitize_filename(
    original_filename: str,
    *,
    max_length: int = 220,
) -> str:
    """Return an ASCII-safe filename while rejecting traversal attempts."""
    if not isinstance(original_filename, str):
        raise UnsafeFilenameError("Filename must be a string.")
    value = unicodedata.normalize("NFKC", original_filename).strip()
    if (
        not value
        or len(value) > 1024
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
        or "/" in value
        or "\\" in value
        or ":" in value
        or value in {".", ".."}
        or ".." in PurePosixPath(value).parts
    ):
        raise UnsafeFilenameError(
            "Filename must not contain a path or control characters."
        )

    ascii_name = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = _UNSAFE_FILENAME.sub("_", ascii_name)
    ascii_name = _REPEATED_UNDERSCORE.sub("_", ascii_name)
    ascii_name = ascii_name.strip(" ._")

    dot_index = ascii_name.rfind(".")
    if dot_index > 0:
        stem = ascii_name[:dot_index].rstrip(" ._")
        extension = ascii_name[dot_index:].lower()
    else:
        stem = ascii_name
        extension = ""
    stem = stem or "document"
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"

    available_stem = max(1, max_length - len(extension))
    sanitized = f"{stem[:available_stem]}{extension}"
    if not sanitized or len(sanitized) > max_length:
        raise UnsafeFilenameError("Filename cannot be sanitized safely.")
    return sanitized


class StoragePathService:
    """Generate opaque, collision-resistant relative storage keys."""

    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        self.documents_prefix = resolved.storage_documents_prefix
        self.temp_prefix = resolved.storage_temp_prefix
        self.quarantine_prefix = resolved.storage_quarantine_prefix
        self.deleted_prefix = resolved.storage_deleted_prefix

    @staticmethod
    def sanitize_filename(original_filename: str) -> str:
        return sanitize_filename(original_filename)

    def temporary_key(
        self,
        session_id: UUID,
        item_id: UUID,
        filename: str,
    ) -> str:
        safe_name = sanitize_filename(filename)
        return self._join(
            self.temp_prefix,
            str(session_id),
            f"{item_id}_{safe_name}",
        )

    def temp_key(
        self,
        session_id: UUID,
        item_id: UUID,
        filename: str,
    ) -> str:
        return self.temporary_key(session_id, item_id, filename)

    def original_key(
        self,
        document_id: UUID,
        revision_id: UUID,
        file_id: UUID,
        filename: str,
        *,
        at: datetime | None = None,
    ) -> str:
        safe_name = sanitize_filename(filename)
        timestamp = (at or datetime.now(UTC)).astimezone(UTC)
        return self._join(
            self.documents_prefix,
            f"{timestamp.year:04d}",
            f"{timestamp.month:02d}",
            str(document_id),
            str(revision_id),
            f"{file_id}_{safe_name}",
        )

    def permanent_key(
        self,
        document_id: UUID,
        revision_id: UUID,
        file_id: UUID,
        filename: str,
        *,
        at: datetime | None = None,
    ) -> str:
        return self.original_key(
            document_id,
            revision_id,
            file_id,
            filename,
            at=at,
        )

    def quarantine_key(
        self,
        session_id: UUID,
        item_id: UUID,
        filename: str,
        *,
        at: datetime | None = None,
    ) -> str:
        safe_name = sanitize_filename(filename)
        timestamp = (at or datetime.now(UTC)).astimezone(UTC)
        return self._join(
            self.quarantine_prefix,
            f"{timestamp.year:04d}",
            f"{timestamp.month:02d}",
            str(session_id),
            f"{item_id}_{safe_name}",
        )

    def deleted_key(
        self,
        document_id: UUID,
        revision_id: UUID,
        file_id: UUID,
        filename: str,
        *,
        at: datetime | None = None,
    ) -> str:
        safe_name = sanitize_filename(filename)
        timestamp = (at or datetime.now(UTC)).astimezone(UTC)
        return self._join(
            self.deleted_prefix,
            f"{timestamp.year:04d}",
            f"{timestamp.month:02d}",
            str(document_id),
            str(revision_id),
            f"{file_id}_{safe_name}",
        )

    @staticmethod
    def _join(*parts: str) -> str:
        return PurePosixPath(*parts).as_posix()
