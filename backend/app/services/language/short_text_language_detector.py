"""Bounded Indonesian and English lexical signals for hybrid decisions."""

from __future__ import annotations

import re

from app.models.language_block_result import LanguageCode

_WORD_RE = re.compile(r"[^\W\d_]+", flags=re.UNICODE)

_INDONESIAN_WORDS = frozenset(
    {
        "adalah",
        "agar",
        "akan",
        "atau",
        "dalam",
        "dan",
        "dari",
        "dengan",
        "harus",
        "ini",
        "oleh",
        "pada",
        "sebagai",
        "setiap",
        "tidak",
        "untuk",
        "yang",
    }
)
_ENGLISH_WORDS = frozenset(
    {
        "and",
        "document",
        "for",
        "must",
        "procedure",
        "shall",
        "that",
        "the",
        "this",
        "with",
    }
)
_INDONESIAN_AFFIXES = (
    "ber",
    "di",
    "ke",
    "mem",
    "men",
    "peng",
    "per",
    "ter",
)
_INDONESIAN_SUFFIXES = ("kan", "nya")


class ShortTextLanguageDetector:
    """Return bounded evidence; never makes the final classification."""

    def signal_scores(self, text: str) -> dict[LanguageCode, float]:
        words = [match.group(0).casefold() for match in _WORD_RE.finditer(text)]
        if not words:
            return {
                LanguageCode.INDONESIAN: 0.0,
                LanguageCode.ENGLISH: 0.0,
            }
        indonesian_hits = sum(word in _INDONESIAN_WORDS for word in words)
        english_hits = sum(word in _ENGLISH_WORDS for word in words)
        affix_hits = sum(
            len(word) >= 6
            and (
                word.startswith(_INDONESIAN_AFFIXES)
                or word.endswith(_INDONESIAN_SUFFIXES)
            )
            for word in words
        )
        denominator = max(2.0, min(float(len(words)), 8.0))
        return {
            LanguageCode.INDONESIAN: min(
                1.0,
                (indonesian_hits + 0.35 * affix_hits) / denominator,
            ),
            LanguageCode.ENGLISH: min(
                1.0,
                english_hits / denominator,
            ),
        }

    @staticmethod
    def word_count(text: str) -> int:
        return len(_WORD_RE.findall(text))
