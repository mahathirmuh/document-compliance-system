"""Bounded cleanup for worker-owned OCR temporary directories."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from pathlib import Path


class OCRTemporaryCleanupService:
    """Remove only direct temporary children created with the OCR prefix."""

    directory_prefix = "document-ocr-"

    def __init__(self, base_directory: Path | None = None) -> None:
        self.base_directory = (
            base_directory.resolve()
            if base_directory is not None
            else Path(tempfile.gettempdir()).resolve()
        )

    async def cleanup_stale(self, retention_hours: int) -> list[Path]:
        """Delete abandoned OCR work directories older than the retention."""
        return await asyncio.to_thread(
            self._cleanup_stale_sync,
            retention_hours,
        )

    async def remove_work_directory(self, path: Path) -> bool:
        """Best-effort removal of one exact, validated OCR work directory."""
        return await asyncio.to_thread(
            self._remove_validated_directory,
            path,
        )

    def _cleanup_stale_sync(self, retention_hours: int) -> list[Path]:
        if retention_hours < 1:
            raise ValueError("OCR temporary retention must be at least one hour.")
        cutoff = time.time() - (retention_hours * 60 * 60)
        removed: list[Path] = []
        try:
            candidates = list(self.base_directory.iterdir())
        except OSError:
            return removed
        for candidate in candidates:
            if not self._is_owned_directory(candidate):
                continue
            try:
                if candidate.stat().st_mtime > cutoff:
                    continue
            except OSError:
                continue
            if self._remove_validated_directory(candidate):
                removed.append(candidate)
        return removed

    def _remove_validated_directory(self, path: Path) -> bool:
        if not self._is_owned_directory(path):
            return False
        try:
            shutil.rmtree(path)
        except OSError:
            return False
        return not path.exists()

    def _is_owned_directory(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return (
            resolved.parent == self.base_directory
            and resolved.name.startswith(self.directory_prefix)
            and resolved.name != self.directory_prefix
            and resolved.is_dir()
            and not resolved.is_symlink()
        )
