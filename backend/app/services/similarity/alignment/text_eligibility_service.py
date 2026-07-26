"""Conservative filtering for content that cannot support semantics."""

from __future__ import annotations

import re
import unicodedata

from app.models.similarity_enums import SimilarityAnalysisStatus
from app.schemas.similarity_internal import TextEligibilityResult

_URL_RE = re.compile(r"(?i)^\s*(?:https?://|www\.)\S+\s*$")
_NUMERIC_RE = re.compile(r"^(?=.*\d)[\d\s+\-–—.,:%‰/()]+$")
_UPPER_CODE_RE = re.compile(
    r"^(?=.{2,80}$)(?=.*[0-9._:/\\-])"
    r"[A-Z0-9][A-Z0-9._:/\\-]*(?:\s+[A-Z0-9._:/\\-]+){0,2}$"
)
_STRUCTURED_CODE_RE = re.compile(
    r"(?i)^(?=.{2,80}$)(?=.*\d)(?=.*[._:/\\-])[a-z0-9._:/\\-]+$"
)


class TextEligibilityService:
    def __init__(
        self,
        *,
        minimum_characters: int = 10,
        skip_code_like_text: bool = True,
        skip_numeric_only_text: bool = True,
    ) -> None:
        self.minimum_characters = max(1, minimum_characters)
        self.skip_code_like_text = skip_code_like_text
        self.skip_numeric_only_text = skip_numeric_only_text

    def evaluate(self, text: str) -> TextEligibilityResult:
        normalized = " ".join(
            unicodedata.normalize("NFKC", text or "").split()
        )
        count = len(normalized)
        if not normalized:
            return self._ineligible(
                normalized,
                "EMPTY_TEXT",
                SimilarityAnalysisStatus.INSUFFICIENT_CONTENT,
            )
        if _URL_RE.fullmatch(normalized):
            return self._ineligible(
                normalized,
                "URL_ONLY_TEXT",
                SimilarityAnalysisStatus.SKIPPED_UNSUPPORTED,
            )
        if not any(character.isalnum() for character in normalized):
            return self._ineligible(
                normalized,
                "PUNCTUATION_ONLY_TEXT",
                SimilarityAnalysisStatus.SKIPPED_UNSUPPORTED,
            )
        if (
            self.skip_numeric_only_text
            and _NUMERIC_RE.fullmatch(normalized)
        ):
            return self._ineligible(
                normalized,
                "NUMERIC_ONLY_TEXT",
                SimilarityAnalysisStatus.SKIPPED_UNSUPPORTED,
            )
        if self.skip_code_like_text and (
            _UPPER_CODE_RE.fullmatch(normalized)
            or _STRUCTURED_CODE_RE.fullmatch(normalized)
        ):
            return self._ineligible(
                normalized,
                "CODE_ONLY_TEXT",
                SimilarityAnalysisStatus.SKIPPED_UNSUPPORTED,
            )
        if count < self.minimum_characters:
            return self._ineligible(
                normalized,
                "TEXT_TOO_SHORT",
                SimilarityAnalysisStatus.SKIPPED_TOO_SHORT,
            )
        return TextEligibilityResult(
            eligible=True,
            status=SimilarityAnalysisStatus.COMPLETED,
            reason=None,
            normalized_text=normalized,
            character_count=count,
        )

    @staticmethod
    def _ineligible(
        normalized: str,
        reason: str,
        status: SimilarityAnalysisStatus,
    ) -> TextEligibilityResult:
        return TextEligibilityResult(
            eligible=False,
            status=status,
            reason=reason,
            normalized_text=normalized,
            character_count=len(normalized),
        )
