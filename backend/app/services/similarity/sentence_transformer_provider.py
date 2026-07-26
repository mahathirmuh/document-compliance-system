"""Lazy, offline-only sentence-transformer provider."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from app.services.similarity.base_similarity_provider import (
    BaseSimilarityProvider,
    SimilarityProviderError,
    SimilarityProviderUnavailable,
)


class SentenceTransformerProvider(BaseSimilarityProvider):
    """Load an explicitly installed local model on first worker use."""

    def __init__(
        self,
        *,
        model_name: str,
        model_path: str | Path,
        device: str = "cpu",
        batch_size: int = 32,
        maximum_sequence_length: int = 512,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name.strip()
        self.model_path = Path(model_path).expanduser()
        self.device = device.strip() or "cpu"
        self.batch_size = max(1, batch_size)
        self.maximum_sequence_length = max(8, maximum_sequence_length)
        self.normalize_embeddings = normalize_embeddings
        self._model: Any | None = None
        self._load_lock = threading.Lock()
        self._load_error: str | None = None

    async def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = await asyncio.to_thread(self._load_model)
        try:
            vectors = await asyncio.to_thread(
                model.encode,
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
            )
        except Exception as exc:
            raise SimilarityProviderError(
                "The local similarity model could not encode the text."
            ) from exc
        output = vectors.tolist() if hasattr(vectors, "tolist") else vectors
        return [
            [float(value) for value in vector]
            for vector in output
        ]

    def get_provider_info(self) -> dict[str, object]:
        metadata = self._read_metadata()
        version = metadata.get("modelVersion") or metadata.get("revision")
        return {
            "provider": "sentence_transformer",
            "modelName": self.model_name,
            "modelVersion": str(version) if version else None,
            "device": self.device,
            "maximumSequenceLength": self.maximum_sequence_length,
            "normalizeEmbeddings": self.normalize_embeddings,
            "localOnly": True,
            "ready": self.is_ready(),
            "loadError": self._load_error,
        }

    def is_ready(self) -> bool:
        if self._model is not None:
            return True
        path = self._resolved_model_path()
        return path.is_dir() and (
            (path / "config.json").is_file()
            or (path / "modules.json").is_file()
        )

    def _resolved_model_path(self) -> Path:
        if (
            (self.model_path / "config.json").is_file()
            or (self.model_path / "modules.json").is_file()
        ):
            return self.model_path
        safe_name = self.model_name.replace("/", "--")
        candidate = self.model_path / safe_name
        return candidate if candidate.exists() else self.model_path

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            local_path = self._resolved_model_path()
            if not self.is_ready():
                self._load_error = "MODEL_NOT_INSTALLED"
                raise SimilarityProviderUnavailable(
                    "The configured local similarity model is not installed."
                )
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                self._load_error = "DEPENDENCY_NOT_INSTALLED"
                raise SimilarityProviderUnavailable(
                    "The sentence-transformers runtime is not installed."
                ) from exc
            try:
                model = SentenceTransformer(
                    str(local_path),
                    device=self.device,
                    local_files_only=True,
                )
                model.max_seq_length = self.maximum_sequence_length
            except Exception as exc:
                self._load_error = "MODEL_LOAD_FAILED"
                raise SimilarityProviderUnavailable(
                    "The configured local similarity model could not be loaded."
                ) from exc
            self._model = model
            self._load_error = None
            return model

    def _read_metadata(self) -> dict[str, object]:
        path = self._resolved_model_path() / "model-metadata.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
