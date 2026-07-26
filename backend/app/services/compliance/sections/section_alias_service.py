"""Alias normalization and bounded-regex validation for section matching."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

import regex as safe_regex

from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    int_value,
    read,
    string_value,
)

_LEADING_NUMBERING_RE = re.compile(
    r"""
    ^\s*
    (?:
        \d+(?:\.\d+)+(?:[.)\-:]?)
        |
        \(?(?:\d+|[ivxlcdm]+|[a-z])\)?[.)\-:]
    )
    \s*
    """,
    re.IGNORECASE | re.VERBOSE,
)
_TRAILING_SEPARATOR_RE = re.compile(r"[\s:：\-–—]+$")
_WHITESPACE_RE = re.compile(r"\s+")
_NESTED_QUANTIFIER_RE = re.compile(
    r"(?:\([^)]*[+*][^)]*\)|\[[^]]+\][+*])[+*{]",
)
_REPEATED_WILDCARD_RE = re.compile(r"(?:\.\*){2,}|(?:\.\+){2,}")
_BACKREFERENCE_RE = re.compile(r"\\[1-9]")


class DuplicateSectionAliasError(ValueError):
    """Raised when aliases collide after canonical normalization."""


class UnsafeSectionAliasRegexError(ValueError):
    """Raised before an unbounded or high-risk regex can be evaluated."""


def normalise_heading(text: str) -> str:
    """Normalize a possible heading while preserving Han characters."""

    normalized = unicodedata.normalize("NFC", text or "")
    normalized = _LEADING_NUMBERING_RE.sub("", normalized, count=1)
    normalized = _TRAILING_SEPARATOR_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized.casefold()


def has_numbering_prefix(text: str) -> bool:
    return _LEADING_NUMBERING_RE.match(
        unicodedata.normalize("NFC", text or ""),
    ) is not None


class SectionAliasService:
    """Pure helpers shared by CRUD validation and runtime matching."""

    def __init__(
        self,
        *,
        regex_max_length: int = 500,
        regex_timeout_ms: int = 100,
    ) -> None:
        if regex_max_length < 1:
            raise ValueError("regex_max_length must be positive.")
        if regex_timeout_ms < 1:
            raise ValueError("regex_timeout_ms must be positive.")
        self.regex_max_length = regex_max_length
        self.regex_timeout_seconds = regex_timeout_ms / 1000

    @staticmethod
    def normalise(text: str) -> str:
        return normalise_heading(text)

    def validate_regex(self, pattern: str) -> safe_regex.Pattern:
        if len(pattern) > self.regex_max_length:
            raise UnsafeSectionAliasRegexError(
                "Section alias regex exceeds the configured length limit.",
            )
        if not pattern:
            raise UnsafeSectionAliasRegexError(
                "Section alias regex must not be empty.",
            )
        if (
            _NESTED_QUANTIFIER_RE.search(pattern)
            or _REPEATED_WILDCARD_RE.search(pattern)
            or _BACKREFERENCE_RE.search(pattern)
        ):
            raise UnsafeSectionAliasRegexError(
                "Section alias regex contains a high-risk construct.",
            )
        try:
            return safe_regex.compile(pattern, safe_regex.IGNORECASE)
        except safe_regex.error as exc:
            raise UnsafeSectionAliasRegexError(
                f"Invalid section alias regex: {exc.msg}.",
            ) from exc

    def regex_matches(
        self,
        pattern: safe_regex.Pattern,
        *texts: str,
    ) -> bool:
        try:
            return any(
                pattern.search(
                    text,
                    timeout=self.regex_timeout_seconds,
                )
                is not None
                for text in texts
            )
        except TimeoutError:
            return False

    def validate_unique(self, aliases: Sequence[object]) -> None:
        seen: set[tuple[str, str, str, str]] = set()
        for alias in aliases:
            if not bool_value(read(alias, "is_active", True), True):
                continue
            profile = string_value(
                first(alias, "profile_id", "section_alias_profile_id", default=""),
            )
            canonical = string_value(
                read(alias, "canonical_code", ""),
            ).upper()
            language = enum_value(
                read(alias, "language_code", "any"),
                "any",
            ).casefold()
            raw_normalised = first(
                alias,
                "normalised_alias",
                "normalized_alias",
                default=None,
            )
            normalised = (
                string_value(raw_normalised)
                if raw_normalised
                else self.normalise(string_value(read(alias, "alias_text", "")))
            )
            key = (profile, canonical, language, normalised)
            if key in seen:
                raise DuplicateSectionAliasError(
                    "Duplicate active section alias for "
                    f"{canonical}/{language}: {normalised!r}.",
                )
            seen.add(key)

            match_type = enum_value(
                read(alias, "match_type", "EXACT"),
            ).upper()
            is_regex = bool_value(read(alias, "is_regex", False))
            if is_regex or match_type == "REGEX":
                self.validate_regex(
                    string_value(read(alias, "alias_text", "")),
                )

    @staticmethod
    def sort_key(alias: object) -> tuple[int, int, str]:
        match_type = enum_value(read(alias, "match_type", "EXACT")).upper()
        strategy_rank = {
            "EXACT": 0,
            "PREFIX": 1,
            "REGEX": 2,
            "CONTAINS": 3,
            "FUZZY": 4,
        }.get(match_type, 5)
        priority = int_value(read(alias, "priority", 0))
        return (
            strategy_rank,
            -priority,
            string_value(read(alias, "alias_text", "")).casefold(),
        )
