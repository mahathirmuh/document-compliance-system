"""Deterministic, language-neutral text normalization utilities."""

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from app.schemas.extraction import ExtractedContainerData

_WORD_PATTERN = re.compile(r"\S+", flags=re.UNICODE)
_TRAILING_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+$", flags=re.MULTILINE)


def normalize_text(value: str | None) -> str:
    """Apply the deliberately light Phase 6 normalization policy."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", str(value).replace("\x00", ""))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _TRAILING_HORIZONTAL_WHITESPACE.sub("", normalized)
    return normalized.rstrip("\n")


def count_characters(value: str | None) -> int:
    """Count normalized Unicode code points."""
    return len(normalize_text(value))


def count_words(value: str | None) -> int:
    """Count whitespace-delimited tokens without language inference."""
    return len(_WORD_PATTERN.findall(normalize_text(value)))


def calculate_content_hash(containers: Iterable[ExtractedContainerData]) -> str:
    """Hash normalized blocks in a deterministic, unambiguous order."""
    digest = hashlib.sha256()
    ordered_containers = sorted(
        containers,
        key=lambda item: (
            item.container_index,
            item.container_type.value,
            item.name or "",
        ),
    )
    for container in ordered_containers:
        ordered_blocks = sorted(
            container.blocks,
            key=lambda item: (item.block_order, item.source_reference),
        )
        for block in ordered_blocks:
            encoded = block.normalised_text.encode("utf-8")
            digest.update(str(container.container_index).encode("ascii"))
            digest.update(b"\0")
            digest.update(str(block.block_order).encode("ascii"))
            digest.update(b"\0")
            digest.update(str(len(encoded)).encode("ascii"))
            digest.update(b":")
            digest.update(encoded)
            digest.update(b"\0")
    return digest.hexdigest()
