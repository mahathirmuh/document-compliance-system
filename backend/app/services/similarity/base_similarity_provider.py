"""Side-effect-free provider contract for local embedding inference."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod


class SimilarityProviderError(RuntimeError):
    """Controlled provider failure safe for worker classification."""


class SimilarityProviderUnavailable(SimilarityProviderError):
    """The configured local model is not installed or cannot be loaded."""


class BaseSimilarityProvider(ABC):
    """Model inference only: no database, finding, audit, or run mutation."""

    @abstractmethod
    async def encode(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding for every input text."""

    async def calculate_similarity(
        self,
        source_text: str,
        target_text: str,
    ) -> float:
        embeddings = await self.encode([source_text, target_text])
        if len(embeddings) != 2:
            raise SimilarityProviderError(
                "The provider returned an invalid embedding count."
            )
        return self.cosine_similarity(embeddings[0], embeddings[1])

    @abstractmethod
    def get_provider_info(self) -> dict[str, object]:
        """Return bounded, non-secret model metadata."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Perform a lightweight, network-free readiness check."""

    @staticmethod
    def cosine_similarity(
        source: list[float],
        target: list[float],
    ) -> float:
        if not source or len(source) != len(target):
            return 0.0
        dot = sum(left * right for left, right in zip(source, target))
        source_norm = math.sqrt(sum(value * value for value in source))
        target_norm = math.sqrt(sum(value * value for value in target))
        if source_norm == 0 or target_norm == 0:
            return 0.0
        # Cosine can be negative. Public similarity scores are normalized
        # review signals in the [0, 1] range.
        return max(0.0, min(1.0, dot / (source_norm * target_norm)))
