"""Bounded Microsoft Graph transient-error retry policy."""

from __future__ import annotations

import email.utils
import random
from dataclasses import dataclass
from datetime import UTC, datetime

TRANSIENT_GRAPH_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class GraphRetryDecision:
    should_retry: bool
    delay_seconds: float = 0.0


class GraphRetryPolicy:
    def __init__(
        self,
        *,
        maximum_retries: int = 5,
        base_seconds: float = 2.0,
        maximum_seconds: float = 120.0,
        jitter_ratio: float = 0.2,
        random_source: random.Random | None = None,
    ) -> None:
        if maximum_retries < 0:
            raise ValueError("maximum_retries cannot be negative.")
        if base_seconds <= 0 or maximum_seconds <= 0:
            raise ValueError("Retry delays must be positive.")
        if not 0 <= jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between zero and one.")
        self.maximum_retries = maximum_retries
        self.base_seconds = base_seconds
        self.maximum_seconds = maximum_seconds
        self.jitter_ratio = jitter_ratio
        self._random = random_source or random.SystemRandom()

    def decide(
        self,
        *,
        attempt: int,
        status_code: int | None,
        retry_after: str | None = None,
        transient_transport_error: bool = False,
    ) -> GraphRetryDecision:
        if attempt >= self.maximum_retries:
            return GraphRetryDecision(False)
        if not transient_transport_error and (
            status_code not in TRANSIENT_GRAPH_STATUSES
        ):
            return GraphRetryDecision(False)

        header_delay = self._retry_after_seconds(retry_after)
        if header_delay is not None:
            return GraphRetryDecision(
                True,
                min(self.maximum_seconds, max(0.0, header_delay)),
            )
        exponential = min(
            self.maximum_seconds,
            self.base_seconds * (2**attempt),
        )
        jitter = exponential * self.jitter_ratio * self._random.random()
        return GraphRetryDecision(
            True,
            min(self.maximum_seconds, exponential + jitter),
        )

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        stripped = value.strip()
        try:
            return max(0.0, float(stripped))
        except ValueError:
            pass
        try:
            parsed = email.utils.parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(
            0.0,
            (parsed.astimezone(UTC) - datetime.now(UTC)).total_seconds(),
        )
