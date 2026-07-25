"""Bounded PDF and Office Open XML signature inspection."""

from __future__ import annotations

import asyncio
import stat
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO

PDF_MAGIC = b"%PDF-"
OOXML_MAGIC = b"PK"
DOCX_REQUIRED_ENTRIES = frozenset(
    {"[Content_Types].xml", "word/document.xml"}
)
XLSX_REQUIRED_ENTRIES = frozenset(
    {"[Content_Types].xml", "xl/workbook.xml"}
)
DEFAULT_MAX_ENTRIES = 10_000
DEFAULT_MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 1000.0

FileSource = str | Path | BinaryIO


class FileSignatureError(ValueError):
    """Content is unsupported, corrupt, ambiguous, or unsafe."""


@contextmanager
def _open_source(source: FileSource) -> Iterator[BinaryIO]:
    if isinstance(source, (str, Path)):
        with Path(source).open("rb") as stream:
            yield stream
        return

    try:
        position = source.tell()
        source.seek(0)
    except (AttributeError, OSError) as exc:
        raise FileSignatureError(
            "File signature source must be seekable."
        ) from exc
    try:
        yield source
    finally:
        source.seek(position)


def _safe_zip_name(filename: str) -> str:
    if not filename or "\x00" in filename or "\\" in filename:
        raise FileSignatureError("OOXML archive contains an unsafe path.")
    path = PurePosixPath(filename)
    if path.is_absolute() or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise FileSignatureError("OOXML archive contains an unsafe path.")
    return path.as_posix().rstrip("/")


def _inspect_ooxml_archive(
    source: FileSource,
    *,
    max_entries: int,
    max_uncompressed_size: int,
    max_compression_ratio: float,
) -> frozenset[str]:
    if (
        max_entries <= 0
        or max_uncompressed_size <= 0
        or max_compression_ratio <= 0
    ):
        raise ValueError("OOXML safety limits must be positive.")

    try:
        with _open_source(source) as stream, zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > max_entries:
                raise FileSignatureError(
                    "OOXML archive entry count exceeds the safety limit."
                )

            names: set[str] = set()
            canonical_names: set[str] = set()
            total_uncompressed = 0
            total_compressed = 0
            for entry in entries:
                safe_name = _safe_zip_name(entry.filename)
                canonical_name = safe_name.casefold()
                if canonical_name in canonical_names:
                    raise FileSignatureError(
                        "OOXML archive contains duplicate paths."
                    )
                canonical_names.add(canonical_name)
                names.add(safe_name)

                unix_mode = (entry.external_attr >> 16) & 0o170000
                if unix_mode == stat.S_IFLNK:
                    raise FileSignatureError(
                        "OOXML archive must not contain symbolic links."
                    )
                if entry.flag_bits & 0x1:
                    raise FileSignatureError(
                        "Encrypted OOXML archives are not supported."
                    )
                if entry.file_size < 0 or entry.compress_size < 0:
                    raise FileSignatureError(
                        "OOXML archive contains invalid entry sizes."
                    )

                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size
                if total_uncompressed > max_uncompressed_size:
                    raise FileSignatureError(
                        "OOXML uncompressed size exceeds the safety limit."
                    )
                if entry.file_size:
                    if not entry.compress_size:
                        raise FileSignatureError(
                            "OOXML entry has an unsafe compression ratio."
                        )
                    ratio = entry.file_size / entry.compress_size
                    if ratio > max_compression_ratio:
                        raise FileSignatureError(
                            "OOXML entry compression ratio is unsafe."
                        )

            if total_uncompressed and (
                not total_compressed
                or total_uncompressed / total_compressed
                > max_compression_ratio
            ):
                raise FileSignatureError(
                    "OOXML archive compression ratio is unsafe."
                )

            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise FileSignatureError(
                    "OOXML archive contains corrupt content."
                )
            return frozenset(names)
    except FileSignatureError:
        raise
    except (
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise FileSignatureError(
            "File is not a valid Office Open XML archive."
        ) from exc


def validate_pdf_signature(source: FileSource) -> None:
    """Require the standard PDF header at byte zero."""
    with _open_source(source) as stream:
        if stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise FileSignatureError("File does not have a valid PDF header.")


def validate_office_open_xml(
    source: FileSource,
    expected_type: str,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> None:
    """Validate OOXML ZIP safety and the required DOCX/XLSX structure."""
    normalized_type = expected_type.strip().lower().lstrip(".")
    required = {
        "docx": DOCX_REQUIRED_ENTRIES,
        "xlsx": XLSX_REQUIRED_ENTRIES,
    }.get(normalized_type)
    if required is None:
        raise ValueError("expected_type must be 'docx' or 'xlsx'.")

    names = _inspect_ooxml_archive(
        source,
        max_entries=max_entries,
        max_uncompressed_size=max_uncompressed_size,
        max_compression_ratio=max_compression_ratio,
    )
    if not required.issubset(names):
        raise FileSignatureError(
            f"File does not contain the required {normalized_type.upper()} "
            "structure."
        )


def detect_file_type(
    source: FileSource,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> str:
    """Return ``pdf``, ``docx``, or ``xlsx`` after structural validation."""
    with _open_source(source) as stream:
        header = stream.read(len(PDF_MAGIC))
    if header.startswith(PDF_MAGIC):
        validate_pdf_signature(source)
        return "pdf"
    if not header.startswith(OOXML_MAGIC):
        raise FileSignatureError("Unsupported or invalid file signature.")

    names = _inspect_ooxml_archive(
        source,
        max_entries=max_entries,
        max_uncompressed_size=max_uncompressed_size,
        max_compression_ratio=max_compression_ratio,
    )
    has_docx = DOCX_REQUIRED_ENTRIES.issubset(names)
    has_xlsx = XLSX_REQUIRED_ENTRIES.issubset(names)
    if has_docx == has_xlsx:
        raise FileSignatureError(
            "OOXML structure is unsupported or ambiguous."
        )
    return "docx" if has_docx else "xlsx"


async def detect_file_type_async(
    source: FileSource,
    **limits: float,
) -> str:
    return await asyncio.to_thread(detect_file_type, source, **limits)


class FileSignatureService:
    """Configurable façade for signature validation."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
        max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    ) -> None:
        self.max_entries = max_entries
        self.max_uncompressed_size = max_uncompressed_size
        self.max_compression_ratio = max_compression_ratio

    def detect_file_type(self, source: FileSource) -> str:
        return detect_file_type(
            source,
            max_entries=self.max_entries,
            max_uncompressed_size=self.max_uncompressed_size,
            max_compression_ratio=self.max_compression_ratio,
        )

    async def detect_file_type_async(self, source: FileSource) -> str:
        return await asyncio.to_thread(self.detect_file_type, source)

    def validate_pdf_signature(self, source: FileSource) -> None:
        validate_pdf_signature(source)

    def validate_office_open_xml(
        self,
        source: FileSource,
        expected_type: str,
    ) -> None:
        validate_office_open_xml(
            source,
            expected_type,
            max_entries=self.max_entries,
            max_uncompressed_size=self.max_uncompressed_size,
            max_compression_ratio=self.max_compression_ratio,
        )
