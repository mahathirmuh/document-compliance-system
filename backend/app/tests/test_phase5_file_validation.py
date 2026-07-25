"""Security-focused tests for Phase 5 validation, signatures, and hashes."""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from app.core.config import Settings
from app.core.exceptions import ApplicationError
from app.services.documents.file_hash_service import (
    calculate_stream_sha256,
)
from app.services.documents.file_signature_service import (
    FileSignatureError,
    FileSignatureService,
    detect_file_type,
    validate_office_open_xml,
)
from app.services.documents.file_validation_service import (
    MIME_TYPES_BY_EXTENSION,
    FileValidationService,
)
from app.services.storage.local_storage import LocalStorage

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def _ooxml_bytes(kind: str) -> bytes:
    required_path = {
        "docx": "word/document.xml",
        "xlsx": "xl/workbook.xml",
        "pptx": "ppt/presentation.xml",
    }[kind]
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(required_path, "<root/>")
    return output.getvalue()


def _settings(**overrides) -> Settings:
    return Settings(
        database_url=(
            "postgresql+asyncpg://user:password@localhost:5432/app"
        ),
        **overrides,
    )


@pytest.mark.parametrize(
    ("filename", "mime_type", "payload", "extension"),
    [
        (
            "Policy.pdf",
            MIME_TYPES_BY_EXTENSION["pdf"],
            PDF_BYTES,
            "pdf",
        ),
        (
            "Procedure.docx",
            MIME_TYPES_BY_EXTENSION["docx"],
            _ooxml_bytes("docx"),
            "docx",
        ),
        (
            "Register.xlsx",
            MIME_TYPES_BY_EXTENSION["xlsx"],
            _ooxml_bytes("xlsx"),
            "xlsx",
        ),
    ],
)
@pytest.mark.asyncio
async def test_valid_pdf_docx_and_xlsx_are_accepted(
    filename: str,
    mime_type: str,
    payload: bytes,
    extension: str,
) -> None:
    result = await FileValidationService(_settings()).validate_stream(
        io.BytesIO(payload),
        original_filename=filename,
        declared_mime_type=mime_type,
    )

    assert result.extension == extension
    assert result.detected_mime_type == MIME_TYPES_BY_EXTENSION[extension]
    assert result.file_size == len(payload)
    assert result.sha256_hash == hashlib.sha256(payload).hexdigest()


@pytest.mark.asyncio
async def test_validate_storage_remains_provider_abstract(
    tmp_path,
) -> None:
    storage = LocalStorage(tmp_path)
    key = "documents/temporary/session/file.pdf"
    await storage.save(io.BytesIO(PDF_BYTES), key)

    result = await FileValidationService(_settings()).validate_storage(
        storage,
        key,
        original_filename="File.pdf",
        declared_mime_type=MIME_TYPES_BY_EXTENSION["pdf"],
    )

    assert result.file_size == len(PDF_BYTES)
    assert result.extension == "pdf"


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("slides.pptx", "application/vnd.ms-powerpoint"),
        ("photo.jpg", "image/jpeg"),
        ("notes.txt", "text/plain"),
    ],
)
def test_unsupported_extensions_are_rejected(
    filename: str,
    mime_type: str,
) -> None:
    with pytest.raises(ApplicationError) as raised:
        FileValidationService(_settings()).validate_upload_metadata(
            filename,
            mime_type,
        )
    assert raised.value.status_code == 415


@pytest.mark.asyncio
async def test_declared_mime_mismatch_is_rejected() -> None:
    with pytest.raises(ApplicationError) as raised:
        await FileValidationService(_settings()).validate_stream(
            io.BytesIO(PDF_BYTES),
            original_filename="File.pdf",
            declared_mime_type="application/octet-stream",
        )
    assert raised.value.status_code == 415


@pytest.mark.asyncio
async def test_fake_pdf_and_extension_signature_mismatch_are_rejected() -> None:
    validator = FileValidationService(_settings())
    with pytest.raises(ApplicationError) as fake_pdf:
        await validator.validate_stream(
            io.BytesIO(b"not a pdf"),
            original_filename="File.pdf",
            declared_mime_type=MIME_TYPES_BY_EXTENSION["pdf"],
        )
    assert fake_pdf.value.status_code == 415

    with pytest.raises(ApplicationError) as mismatch:
        await validator.validate_stream(
            io.BytesIO(_ooxml_bytes("docx")),
            original_filename="File.xlsx",
            declared_mime_type=MIME_TYPES_BY_EXTENSION["xlsx"],
        )
    assert mismatch.value.status_code == 415


@pytest.mark.parametrize("extension", ["docx", "xlsx"])
@pytest.mark.asyncio
async def test_corrupt_ooxml_is_rejected(extension: str) -> None:
    with pytest.raises(ApplicationError) as raised:
        await FileValidationService(_settings()).validate_stream(
            io.BytesIO(b"PK\x03\x04corrupt"),
            original_filename=f"File.{extension}",
            declared_mime_type=MIME_TYPES_BY_EXTENSION[extension],
        )
    assert raised.value.status_code == 415


def test_pptx_internal_structure_is_not_treated_as_supported_ooxml() -> None:
    with pytest.raises(FileSignatureError):
        detect_file_type(io.BytesIO(_ooxml_bytes("pptx")))


def test_zip_bomb_like_ratio_and_traversal_are_rejected() -> None:
    compressed = io.BytesIO()
    with zipfile.ZipFile(
        compressed,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "A" * 100_000)

    service = FileSignatureService(max_compression_ratio=5)
    with pytest.raises(FileSignatureError, match="compression ratio"):
        service.validate_office_open_xml(compressed, "docx")

    traversing = io.BytesIO()
    with zipfile.ZipFile(traversing, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<root/>")
        archive.writestr("../outside.xml", "<root/>")
    with pytest.raises(FileSignatureError, match="unsafe path"):
        validate_office_open_xml(traversing, "docx")


def test_ooxml_required_parts_are_case_sensitive() -> None:
    wrong_case = io.BytesIO()
    with zipfile.ZipFile(wrong_case, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("WORD/DOCUMENT.XML", "<root/>")

    payload = wrong_case.getvalue()
    with pytest.raises(FileSignatureError, match="required DOCX"):
        validate_office_open_xml(io.BytesIO(payload), "docx")
    with pytest.raises(FileSignatureError, match="unsupported or ambiguous"):
        detect_file_type(io.BytesIO(payload))


@pytest.mark.asyncio
async def test_oversized_file_is_rejected_with_413() -> None:
    payload = PDF_BYTES + (b"A" * 1024 * 1024)
    validator = FileValidationService(
        _settings(document_max_file_size_mb=1)
    )

    with pytest.raises(ApplicationError) as raised:
        await validator.validate_stream(
            io.BytesIO(payload),
            original_filename="Large.pdf",
            declared_mime_type=MIME_TYPES_BY_EXTENSION["pdf"],
        )
    assert raised.value.status_code == 413


@pytest.mark.parametrize(
    "filename",
    ["../../secret.pdf", r"..\..\secret.pdf", "/tmp/file.pdf"],
)
def test_unsafe_client_filename_is_rejected(filename: str) -> None:
    with pytest.raises(ApplicationError) as raised:
        FileValidationService(_settings()).validate_upload_metadata(
            filename,
            MIME_TYPES_BY_EXTENSION["pdf"],
        )
    assert raised.value.status_code == 422


class _NonSeekableStream:
    def __init__(self, payload: bytes) -> None:
        self._stream = io.BytesIO(payload)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def seekable(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_nonseekable_stream_is_spooled_without_full_memory_contract() -> None:
    result = await FileValidationService(_settings()).validate_stream(
        _NonSeekableStream(PDF_BYTES),  # type: ignore[arg-type]
        original_filename="Stream.pdf",
        declared_mime_type=MIME_TYPES_BY_EXTENSION["pdf"],
    )
    assert result.sha256_hash == hashlib.sha256(PDF_BYTES).hexdigest()


def test_sha256_streaming_is_consistent_and_restores_position() -> None:
    source = io.BytesIO(b"prefix-payload")
    source.seek(4)

    first = calculate_stream_sha256(source, chunk_size=2)
    second = calculate_stream_sha256(source, chunk_size=7)

    assert first == second == hashlib.sha256(b"prefix-payload").hexdigest()
    assert source.tell() == 4
    assert calculate_stream_sha256(io.BytesIO(b"different")) != first
