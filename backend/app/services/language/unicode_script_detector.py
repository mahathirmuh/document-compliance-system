"""Character-based Unicode script statistics, including Han detection."""

from __future__ import annotations

import unicodedata

from app.schemas.language_internal import (
    ScriptStatisticsData,
    UnicodeDominantScript,
)


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2FA1F
    )


def _is_latin(character: str) -> bool:
    if not unicodedata.category(character).startswith("L"):
        return False
    return "LATIN" in unicodedata.name(character, "")


class UnicodeScriptDetector:
    """Count script and non-letter categories without word segmentation."""

    def analyse(self, text: str) -> ScriptStatisticsData:
        latin = 0
        han = 0
        digits = 0
        punctuation = 0
        symbols = 0
        other_letters = 0
        for character in text:
            category = unicodedata.category(character)
            if _is_han(character):
                han += 1
            elif _is_latin(character):
                latin += 1
            elif category.startswith("L"):
                other_letters += 1
            elif category.startswith("N"):
                digits += 1
            elif category.startswith("P"):
                punctuation += 1
            elif category.startswith("S"):
                symbols += 1

        linguistic = latin + han + other_letters
        han_ratio = han / linguistic if linguistic else 0.0
        latin_ratio = latin / linguistic if linguistic else 0.0
        if linguistic == 0:
            dominant = UnicodeDominantScript.NONE
        elif latin and han and min(han_ratio, latin_ratio) >= 0.15:
            dominant = UnicodeDominantScript.MIXED
        elif han >= max(latin, other_letters):
            dominant = UnicodeDominantScript.HAN
        elif latin >= max(han, other_letters):
            dominant = UnicodeDominantScript.LATIN
        else:
            dominant = UnicodeDominantScript.OTHER
        return ScriptStatisticsData(
            latin_character_count=latin,
            han_character_count=han,
            digit_count=digits,
            punctuation_count=punctuation,
            symbol_count=symbols,
            other_letter_count=other_letters,
            total_character_count=len(text),
            dominant_script=dominant,
            han_ratio=han_ratio,
            latin_ratio=latin_ratio,
        )
