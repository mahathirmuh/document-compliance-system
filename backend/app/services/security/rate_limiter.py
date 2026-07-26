"""Atomic Redis-backed rate limiting with privacy-preserving keys."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from app.core.exceptions import ApplicationError
from app.schemas.common import ErrorDetail

_ATOMIC_INCREMENT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class AsyncRedisScriptClient(Protocol):
    async def eval(
        self,
        script: str,
        number_of_keys: int,
        *keys_and_args: object,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if (
            not self.name
            or self.limit < 1
            or self.window_seconds < 1
            or self.window_seconds > 86_400
        ):
            raise ValueError("Rate-limit rule is invalid.")


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class RedisRateLimiter:
    def __init__(
        self,
        redis: AsyncRedisScriptClient,
        *,
        namespace: str,
        enabled: bool = True,
        fail_open: bool = False,
    ) -> None:
        self.redis = redis
        self.namespace = namespace.strip(":")
        self.enabled = enabled
        self.fail_open = fail_open
        if not self.namespace:
            raise ValueError("A rate-limit namespace is required.")

    async def check(
        self,
        rule: RateLimitRule,
        *,
        principal: str,
    ) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                retry_after_seconds=0,
            )
        digest = hashlib.sha256(principal.encode("utf-8")).hexdigest()
        key = f"{self.namespace}:rate:{rule.name}:{digest}"
        try:
            raw_result = await self.redis.eval(
                _ATOMIC_INCREMENT_SCRIPT,
                1,
                key,
                rule.window_seconds,
            )
            if (
                not isinstance(raw_result, (list, tuple))
                or len(raw_result) != 2
            ):
                raise TypeError("Redis returned an invalid rate-limit result.")
            count = int(raw_result[0])
            ttl = max(0, int(raw_result[1]))
        except Exception:  # noqa: BLE001 - Redis client errors vary by driver
            if self.fail_open:
                return RateLimitDecision(
                    allowed=True,
                    limit=rule.limit,
                    remaining=rule.limit,
                    retry_after_seconds=0,
                )
            raise ApplicationError(
                "Rate-limit service is unavailable.",
                status_code=503,
                errors=[
                    ErrorDetail(
                        message="Please try again later.",
                        code="REDIS_UNAVAILABLE",
                    )
                ],
            ) from None
        return RateLimitDecision(
            allowed=count <= rule.limit,
            limit=rule.limit,
            remaining=max(0, rule.limit - count),
            retry_after_seconds=ttl if count > rule.limit else 0,
        )

    async def enforce(
        self,
        rule: RateLimitRule,
        *,
        principal: str,
    ) -> RateLimitDecision:
        decision = await self.check(rule, principal=principal)
        if not decision.allowed:
            raise ApplicationError(
                "Rate limit exceeded.",
                status_code=429,
                errors=[
                    ErrorDetail(
                        message=(
                            "Too many requests. Retry after "
                            f"{decision.retry_after_seconds} seconds."
                        ),
                        code="RATE_LIMIT_EXCEEDED",
                    )
                ],
            )
        return decision
