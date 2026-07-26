"""Unicode-safe glossary normalization."""

from __future__ import annotations

import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")


def normalize_term(
    value: str,
    *,
    case_sensitive: bool = False,
) -> str:
    """Normalize compatibility characters and spacing without translation."""

    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    return normalized if case_sensitive else normalized.casefold()


def contains_han(value: str) -> bool:
    return any(
        "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
        for character in value
    )


def is_latin_word_character(value: str) -> bool:
    return bool(value) and (value.isascii() and (value.isalnum() or value == "_"))
