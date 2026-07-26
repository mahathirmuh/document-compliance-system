"""Bounded paragraph/sentence-aware chunking with explicit truncation warnings."""

from __future__ import annotations

import re

from app.schemas.similarity_internal import (
    ChunkingResult,
    TextChunk,
)

_BOUNDARY_RE = re.compile(r"(?:\r?\n\s*\r?\n|[.!?。！？；;]\s+)")


class LongTextChunkingService:
    def __init__(
        self,
        *,
        text_max_characters: int = 12000,
        chunk_max_characters: int = 1500,
        overlap_characters: int = 150,
        maximum_chunks: int = 50,
    ) -> None:
        if text_max_characters < 1 or chunk_max_characters < 1:
            raise ValueError("Similarity text and chunk limits must be positive.")
        if overlap_characters < 0 or overlap_characters >= chunk_max_characters:
            raise ValueError(
                "Chunk overlap must be nonnegative and smaller than a chunk."
            )
        if maximum_chunks < 1:
            raise ValueError("Maximum similarity chunks must be positive.")
        self.text_max_characters = text_max_characters
        self.chunk_max_characters = chunk_max_characters
        self.overlap_characters = overlap_characters
        self.maximum_chunks = maximum_chunks

    def chunk(self, text: str) -> ChunkingResult:
        original = text or ""
        warnings: list[str] = []
        bounded = original
        if len(bounded) > self.text_max_characters:
            bounded = bounded[: self.text_max_characters]
            warnings.append("SIMILARITY_TEXT_CHARACTER_LIMIT_REACHED")
        if len(bounded) <= self.chunk_max_characters:
            return ChunkingResult(
                chunks=(
                    [
                        TextChunk(
                            index=0,
                            text=bounded,
                            start_character=0,
                            end_character=len(bounded),
                        )
                    ]
                    if bounded
                    else []
                ),
                original_character_count=len(original),
                processed_character_count=len(bounded),
                complete=len(bounded) == len(original),
                warnings=warnings,
            )
        chunks: list[TextChunk] = []
        start = 0
        while start < len(bounded) and len(chunks) < self.maximum_chunks:
            hard_end = min(len(bounded), start + self.chunk_max_characters)
            end = self._preferred_end(bounded, start, hard_end)
            if end <= start:
                end = hard_end
            piece = bounded[start:end].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        text=piece,
                        start_character=start,
                        end_character=end,
                    )
                )
            if end >= len(bounded):
                start = end
                break
            start = max(start + 1, end - self.overlap_characters)
        processed = min(start, len(bounded))
        complete = processed >= len(original)
        if start < len(bounded):
            warnings.append("SIMILARITY_MAX_CHUNKS_REACHED")
            processed = chunks[-1].end_character if chunks else 0
            complete = False
        elif len(bounded) < len(original):
            complete = False
        return ChunkingResult(
            chunks=chunks,
            original_character_count=len(original),
            processed_character_count=processed,
            complete=complete,
            warnings=warnings,
        )

    def _preferred_end(self, text: str, start: int, hard_end: int) -> int:
        if hard_end >= len(text):
            return hard_end
        minimum = start + max(1, self.chunk_max_characters // 2)
        candidates = [
            match.end()
            for match in _BOUNDARY_RE.finditer(text, minimum, hard_end)
        ]
        return candidates[-1] if candidates else hard_end
