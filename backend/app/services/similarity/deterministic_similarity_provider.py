"""Deterministic, dependency-free provider for tests and explicit dev use."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

from app.services.similarity.base_similarity_provider import (
    BaseSimilarityProvider,
)

_WORD_RE = re.compile(r"\w+", re.UNICODE)


class DeterministicSimilarityProvider(BaseSimilarityProvider):
    """Stable hashed lexical embeddings; never selected as a silent fallback."""

    def __init__(self, *, dimensions: int = 256) -> None:
        if dimensions < 32:
            raise ValueError("Deterministic embedding dimensions must be >= 32.")
        self.dimensions = dimensions

    async def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._embedding(text) for text in texts]

    def get_provider_info(self) -> dict[str, object]:
        return {
            "provider": "deterministic",
            "modelName": "hashed-lexical-test-provider",
            "modelVersion": "1",
            "dimensions": self.dimensions,
            "localOnly": True,
            "testProvider": True,
        }

    def is_ready(self) -> bool:
        return True

    def _embedding(self, text: str) -> list[float]:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        tokens = _WORD_RE.findall(normalized)
        features = [f"w:{token}" for token in tokens]
        compact = "".join(normalized.split())
        features.extend(
            f"c:{compact[index : index + 3]}"
            for index in range(max(0, len(compact) - 2))
        )
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"),
                digest_size=16,
                person=b"phase9-sim",
            ).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return (
            [value / norm for value in vector]
            if norm
            else vector
        )
