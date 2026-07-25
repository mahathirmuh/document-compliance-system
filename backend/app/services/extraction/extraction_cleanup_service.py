"""Best-effort cleanup for worker-owned temporary extraction files."""

from __future__ import annotations

import asyncio
from pathlib import Path


class ExtractionCleanupService:
    """Remove one explicit worker temporary file without broad recursion."""

    @staticmethod
    async def remove_file(path: Path) -> None:
        await asyncio.to_thread(ExtractionCleanupService._remove_sync, path)

    @staticmethod
    def _remove_sync(path: Path) -> None:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
        except OSError:
            # TemporaryDirectory performs a second cleanup attempt. Extraction
            # correctness must not be replaced by an unsafe broad deletion.
            return

