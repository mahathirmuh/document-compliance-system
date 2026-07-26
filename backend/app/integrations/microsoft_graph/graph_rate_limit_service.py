"""Per-client Graph concurrency gate and low-cardinality counters."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GraphRateLimitService:
    def __init__(self, *, maximum_concurrency: int = 4) -> None:
        if maximum_concurrency <= 0:
            raise ValueError("maximum_concurrency must be positive.")
        self._semaphore = asyncio.Semaphore(maximum_concurrency)
        self._counters: Counter[str] = Counter()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with self._semaphore:
            yield

    async def record(
        self,
        *,
        status_code: int | None = None,
        retry_delay_seconds: float | None = None,
    ) -> None:
        async with self._lock:
            self._counters["requests"] += 1
            if status_code == 429:
                self._counters["rate_limited"] += 1
            if status_code in {500, 502, 503, 504}:
                self._counters["service_unavailable"] += 1
            if retry_delay_seconds is not None:
                self._counters["retry_count"] += 1
                self._counters["retry_delay_milliseconds"] += int(
                    max(0, retry_delay_seconds) * 1000
                )

    async def snapshot(self) -> dict[str, int]:
        async with self._lock:
            return dict(self._counters)
