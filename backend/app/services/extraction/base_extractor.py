"""Format-independent extractor contract and controlled exceptions."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from inspect import isawaitable
from pathlib import Path

from pydantic import JsonValue

from app.schemas.extraction import ExtractedDocumentData, ExtractionContext


class ExtractionError(Exception):
    """A safe, categorized extraction failure suitable for job persistence."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.details = dict(details or {})


class UnsupportedExtractionFormatError(ExtractionError):
    """Raised when no extractor exists for a requested extension."""

    def __init__(self, extension: str) -> None:
        super().__init__(
            "UNSUPPORTED_EXTRACTION_FORMAT",
            "This file format is not supported for content extraction.",
            details={"extension": extension},
        )


class ExtractionResourceLimitError(ExtractionError):
    """Raised before an extractor consumes unsafe amounts of resources."""


class ExtractionCancelledError(ExtractionError):
    """Raised at a safe checkpoint after cancellation is requested."""

    def __init__(self) -> None:
        super().__init__(
            "EXTRACTION_CANCELLED",
            "Document extraction was cancelled.",
        )


class BaseDocumentExtractor(ABC):
    """Pure reader that converts one physical file into intermediate data."""

    @abstractmethod
    def supports(self, extension: str) -> bool:
        """Return whether this extractor supports ``extension``."""

    @abstractmethod
    async def extract(
        self,
        file_path: Path,
        context: dict[str, object],
    ) -> ExtractedDocumentData:
        """Read and normalize a file without mutating application state."""

    @abstractmethod
    async def inspect(self, file_path: Path) -> dict[str, JsonValue]:
        """Return safe, shallow source metadata without persistence."""

    @staticmethod
    def normalize_extension(extension: str) -> str:
        return extension.strip().lower().lstrip(".")

    @staticmethod
    def resolve_context(context: Mapping[str, object] | None) -> ExtractionContext:
        return ExtractionContext.from_mapping(context)

    @staticmethod
    def validate_source_path(
        file_path: Path,
        context: ExtractionContext | None = None,
    ) -> int:
        """Validate existence, regular-file type, and optional byte limit."""
        try:
            stat_result = file_path.stat()
        except OSError as exc:
            raise ExtractionError(
                "FILE_NOT_FOUND_IN_STORAGE",
                "The document file could not be found in storage.",
            ) from exc

        if not file_path.is_file():
            raise ExtractionError(
                "FILE_NOT_FOUND_IN_STORAGE",
                "The document file could not be found in storage.",
            )
        if context is not None and stat_result.st_size > context.maximum_file_size_bytes:
            raise ExtractionResourceLimitError(
                "EXTRACTION_FILE_TOO_LARGE",
                "The document exceeds the configured extraction file-size limit.",
                details={
                    "maximumBytes": context.maximum_file_size_bytes,
                    "actualBytes": stat_result.st_size,
                },
            )
        return stat_result.st_size

    @staticmethod
    async def checkpoint(
        context: ExtractionContext,
        progress: int,
        stage: str,
    ) -> None:
        """Report progress and honor cancellation between safe work units."""
        if context.cancellation_checker is not None:
            cancellation_result = context.cancellation_checker()
            if isawaitable(cancellation_result):
                cancellation_result = await cancellation_result
            if bool(cancellation_result):
                raise ExtractionCancelledError

        if (
            context.progress_callback is not None
            and progress != context._last_reported_progress
        ):
            progress_result = context.progress_callback(progress, stage)
            if isawaitable(progress_result):
                await progress_result
            context._last_reported_progress = progress
