"""Unicode-safe normalization, eligibility, and snapshot hashing."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence

from app.models.language_block_result import (
    LanguageEligibilityReason,
    LanguageEligibilityStatus,
)
from app.schemas.language_internal import (
    LanguageEligibilityData,
    LanguageSourceBlockData,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)

_WHITESPACE_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"(?i)https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(
    r"(?i)[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
)
_CODE_RE = re.compile(
    r"(?i)(?=[a-z0-9._/-]*\d)(?=[a-z0-9._/-]*[a-z])"
    r"[a-z0-9]+(?:[-_./][a-z0-9]+)+"
)


def normalize_language_text(text: str) -> str:
    """Normalize compatibility characters and collapse unsafe whitespace."""
    normalized = unicodedata.normalize("NFKC", text or "")
    return _WHITESPACE_RE.sub(" ", normalized).strip()


class LanguageEligibilityEvaluator:
    """Exclude non-linguistic text before loading the statistical model."""

    def __init__(self, config: LanguageRuntimeConfig) -> None:
        self.config = config

    def evaluate(self, text: str) -> LanguageEligibilityData:
        normalized = normalize_language_text(text)
        if not normalized:
            return self._ineligible(LanguageEligibilityReason.EMPTY)
        if _URL_RE.fullmatch(normalized):
            return self._ineligible(LanguageEligibilityReason.URL_ONLY)
        if _EMAIL_RE.fullmatch(normalized):
            return self._ineligible(LanguageEligibilityReason.EMAIL_ONLY)
        if _CODE_RE.fullmatch(normalized):
            return self._ineligible(
                LanguageEligibilityReason.CODE_LIKE_TEXT
            )
        letter_count = sum(
            unicodedata.category(character).startswith("L")
            for character in normalized
        )
        if letter_count == 0:
            return self._ineligible(LanguageEligibilityReason.NO_LETTERS)
        if (
            len(normalized) < self.config.minimum_characters
            or letter_count < self.config.minimum_alpha_characters
        ):
            return self._ineligible(LanguageEligibilityReason.TOO_SHORT)
        return LanguageEligibilityData(
            status=LanguageEligibilityStatus.ELIGIBLE,
            reason=None,
        )

    @staticmethod
    def _ineligible(
        reason: LanguageEligibilityReason,
    ) -> LanguageEligibilityData:
        return LanguageEligibilityData(
            status=LanguageEligibilityStatus.INELIGIBLE,
            reason=reason,
        )


def calculate_source_content_hash(
    blocks: Sequence[LanguageSourceBlockData],
) -> str:
    """Hash ordered normalized content and provenance without source secrets."""
    digest = hashlib.sha256()
    for block in sorted(
        blocks,
        key=lambda item: (
            item.container_index,
            item.block_order,
            item.source_type.value,
            item.source_reference,
            str(item.extracted_block_id or item.ocr_block_id),
        ),
    ):
        values = (
            block.source_type.value,
            str(block.extracted_block_id or ""),
            str(block.ocr_block_id or ""),
            str(block.container_id or ""),
            str(block.container_index),
            str(block.block_order),
            block.source_reference,
            normalize_language_text(block.normalised_text or block.text),
        )
        digest.update("\x1f".join(values).encode("utf-8"))
        digest.update(b"\x1e")
    return digest.hexdigest()


def calculate_source_snapshot_hash(
    extraction_content_hash: str | None,
    ocr_content_hash: str | None,
) -> str:
    """Hash immutable upstream content hashes for idempotent job reuse."""
    digest = hashlib.sha256()
    digest.update(
        f"extraction:{extraction_content_hash or 'none'}".encode("ascii")
    )
    digest.update(b"\x1f")
    digest.update(f"ocr:{ocr_content_hash or 'none'}".encode("ascii"))
    return digest.hexdigest()
