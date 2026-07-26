"""Select an explicitly configured local similarity provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.similarity.base_similarity_provider import (
    BaseSimilarityProvider,
    SimilarityProviderUnavailable,
)
from app.services.similarity.deterministic_similarity_provider import (
    DeterministicSimilarityProvider,
)
from app.services.similarity.sentence_transformer_provider import (
    SentenceTransformerProvider,
)


def _setting(settings: object, name: str, default: Any) -> Any:
    return getattr(settings, name, default)


class SimilarityProviderFactory:
    """No cloud providers and no implicit model download/fallback."""

    @staticmethod
    def create(settings: object) -> BaseSimilarityProvider:
        provider = str(
            _setting(settings, "similarity_provider", "sentence_transformer")
        ).strip().casefold()
        if provider in {"deterministic", "test"}:
            return DeterministicSimilarityProvider()
        if provider != "sentence_transformer":
            raise SimilarityProviderUnavailable(
                f'Unsupported local similarity provider "{provider}".'
            )
        return SentenceTransformerProvider(
            model_name=str(
                _setting(
                    settings,
                    "similarity_model_name",
                    (
                        "sentence-transformers/"
                        "paraphrase-multilingual-MiniLM-L12-v2"
                    ),
                )
            ),
            model_path=Path(
                str(
                    _setting(
                        settings,
                        "similarity_model_path",
                        "/app/models/similarity",
                    )
                )
            ),
            device=str(_setting(settings, "similarity_device", "cpu")),
            batch_size=int(
                _setting(settings, "similarity_batch_size", 32)
            ),
            maximum_sequence_length=int(
                _setting(
                    settings,
                    "similarity_max_sequence_length",
                    512,
                )
            ),
            normalize_embeddings=bool(
                _setting(
                    settings,
                    "similarity_normalize_embeddings",
                    True,
                )
            ),
        )
