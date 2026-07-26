"""Bounded regex glossary matching with timeout protection."""

from __future__ import annotations

import re

import regex

from app.models.glossary_enums import GlossaryMatchType
from app.services.glossary.matching.exact_term_matcher import MatchSpan

_NESTED_QUANTIFIER = re.compile(
    r"\((?:[^()]|\\.)*[*+](?:[^()]|\\.)*\)\s*(?:[*+?]|\{\d)"
)
_BACKREFERENCE = re.compile(r"(?<!\\)\\[1-9]")
_DANGEROUS_TOKENS = ("(?R", "(?0", "(?&", r"\g<", r"\k<")


class UnsafeGlossaryRegexError(ValueError):
    """Raised when a glossary regex violates safety limits."""


class GlossaryRegexTimeoutError(ValueError):
    """Raised when a bounded local regex exceeds its runtime budget."""


class RegexTermMatcher:
    """Compile and execute only bounded, non-recursive patterns."""

    def __init__(
        self,
        *,
        maximum_length: int = 500,
        timeout_ms: int = 100,
    ) -> None:
        if maximum_length < 1:
            raise ValueError("maximum_length must be positive.")
        if timeout_ms < 1:
            raise ValueError("timeout_ms must be positive.")
        self.maximum_length = maximum_length
        self.timeout_seconds = timeout_ms / 1000

    def validate(
        self,
        pattern: str,
        *,
        case_sensitive: bool = False,
    ) -> regex.Pattern[str]:
        if not pattern:
            raise UnsafeGlossaryRegexError("Regex term must not be empty.")
        if len(pattern) > self.maximum_length:
            raise UnsafeGlossaryRegexError(
                "Regex term exceeds the configured length limit."
            )
        if any(token in pattern for token in _DANGEROUS_TOKENS):
            raise UnsafeGlossaryRegexError(
                "Recursive and subroutine regex constructs are not allowed."
            )
        if _BACKREFERENCE.search(pattern):
            raise UnsafeGlossaryRegexError(
                "Regex backreferences are not allowed."
            )
        if _NESTED_QUANTIFIER.search(pattern):
            raise UnsafeGlossaryRegexError(
                "Nested regex quantifiers are not allowed."
            )
        flags = regex.VERSION1
        if not case_sensitive:
            flags |= regex.IGNORECASE
        try:
            return regex.compile(pattern, flags)
        except regex.error as exc:
            raise UnsafeGlossaryRegexError(
                f"Glossary regex is invalid: {exc}."
            ) from exc

    def find(
        self,
        text: str,
        pattern: str,
        *,
        case_sensitive: bool,
    ) -> list[MatchSpan]:
        compiled = self.validate(pattern, case_sensitive=case_sensitive)
        try:
            return [
                MatchSpan(
                    match.start(),
                    match.end(),
                    GlossaryMatchType.REGEX,
                )
                for match in compiled.finditer(
                    text,
                    timeout=self.timeout_seconds,
                )
                if match.end() > match.start()
            ]
        except TimeoutError as exc:
            raise GlossaryRegexTimeoutError(
                "Glossary regex exceeded its runtime limit."
            ) from exc
