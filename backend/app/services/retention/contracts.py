"""Generic retention candidates and entity handler contract."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.models.data_retention_policy import DataRetentionPolicy


@dataclass(frozen=True, slots=True)
class RetentionCandidate:
    id: UUID
    created_at: datetime
    legal_hold: bool = False
    archived: bool = False
    soft_deleted: bool = False
    sole_copy: bool = False


class RetentionEntityHandler(Protocol):
    supports_archive: bool
    supports_soft_delete: bool

    async def list_candidates(
        self,
        *,
        policy: DataRetentionPolicy,
        archive_cutoff: datetime | None,
        delete_cutoff: datetime,
        limit: int,
    ) -> Sequence[RetentionCandidate]: ...

    async def archive(self, candidate: RetentionCandidate) -> None: ...

    async def soft_delete(self, candidate: RetentionCandidate) -> None: ...

    async def permanently_delete(
        self,
        candidate: RetentionCandidate,
    ) -> None: ...
