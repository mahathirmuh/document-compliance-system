"""Lightweight local similarity fallback used only for revision alignment."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.services.revision_comparison.revision_alignment_service import (
    normalize_revision_text,
)


class RevisionSimilarityService:
    """No cloud calls and no retained embedding vectors."""

    @staticmethod
    def calculate(left: str, right: str) -> float:
        return SequenceMatcher(
            None,
            normalize_revision_text(left),
            normalize_revision_text(right),
        ).ratio()
