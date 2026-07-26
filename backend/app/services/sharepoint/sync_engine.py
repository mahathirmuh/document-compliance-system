"""Deterministic, side-effect-free SharePoint sync planning."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models.sharepoint_enums import (
    ConflictPolicy,
    SyncConflictType,
    SyncDirection,
    SyncItemOperation,
)


@dataclass(frozen=True, slots=True)
class LocalSyncState:
    document_file_id: str | None
    content_hash: str | None
    modified_at: datetime | None
    path: str | None
    deleted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RemoteSyncState:
    item_id: str | None
    etag: str | None
    modified_at: datetime | None
    path: str | None
    deleted: bool = False
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SyncBaseline:
    local_content_hash: str | None
    remote_etag: str | None


@dataclass(frozen=True, slots=True)
class SyncDecision:
    operation: SyncItemOperation
    conflict_type: SyncConflictType | None = None
    reason: str = ""
    create_copy: bool = False


class SharePointSyncEngine:
    """Plan one item without performing network or database I/O."""

    def decide(
        self,
        *,
        direction: SyncDirection,
        conflict_policy: ConflictPolicy,
        local: LocalSyncState | None,
        remote: RemoteSyncState | None,
        baseline: SyncBaseline | None,
    ) -> SyncDecision:
        if local is None and remote is None:
            return SyncDecision(SyncItemOperation.SKIP, reason="No item exists.")
        if local is None:
            assert remote is not None
            if remote.deleted:
                return SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="Remote tombstone has no local counterpart.",
                )
            if direction is SyncDirection.OUTBOUND:
                return SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="Outbound profile ignores remote-only items.",
                )
            return SyncDecision(
                SyncItemOperation.CREATE_LOCAL,
                reason="Remote-only item is eligible for inbound creation.",
            )
        if remote is None:
            if local.deleted:
                return SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="Local tombstone has no remote counterpart.",
                )
            if direction is SyncDirection.INBOUND:
                return SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="Inbound profile ignores local-only items.",
                )
            return SyncDecision(
                SyncItemOperation.CREATE_REMOTE,
                reason="Local-only item is eligible for outbound creation.",
            )

        local_changed = baseline is None or (
            local.content_hash != baseline.local_content_hash
        )
        remote_changed = baseline is None or (
            remote.etag != baseline.remote_etag
        )

        deletion = self._deletion_decision(
            direction=direction,
            local=local,
            remote=remote,
            local_changed=local_changed,
            remote_changed=remote_changed,
        )
        if deletion is not None:
            return deletion

        if direction is SyncDirection.OUTBOUND:
            return (
                SyncDecision(
                    SyncItemOperation.UPDATE_REMOTE,
                    reason="Local content changed.",
                )
                if local_changed
                else SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="No outbound change.",
                )
            )
        if direction is SyncDirection.INBOUND:
            return (
                SyncDecision(
                    SyncItemOperation.UPDATE_LOCAL,
                    reason="Remote content changed.",
                )
                if remote_changed
                else SyncDecision(
                    SyncItemOperation.SKIP,
                    reason="No inbound change.",
                )
            )
        if local_changed and remote_changed:
            return self._resolve_both_modified(
                conflict_policy=conflict_policy,
                local=local,
                remote=remote,
            )
        if local_changed:
            return SyncDecision(
                SyncItemOperation.UPDATE_REMOTE,
                reason="Only local content changed.",
            )
        if remote_changed:
            return SyncDecision(
                SyncItemOperation.UPDATE_LOCAL,
                reason="Only remote content changed.",
            )
        if local.path != remote.path:
            return SyncDecision(
                SyncItemOperation.CONFLICT,
                conflict_type=SyncConflictType.PATH_CONFLICT,
                reason="Local and remote paths differ.",
            )
        return SyncDecision(SyncItemOperation.SKIP, reason="No change.")

    @staticmethod
    def idempotency_key(
        *,
        sync_profile_id: str,
        remote_item_id: str | None,
        remote_etag: str | None,
        local_content_hash: str | None,
        operation: SyncItemOperation,
    ) -> str:
        material = "\x1f".join(
            (
                sync_profile_id,
                remote_item_id or "",
                remote_etag or "",
                local_content_hash or "",
                operation.value,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _deletion_decision(
        self,
        *,
        direction: SyncDirection,
        local: LocalSyncState,
        remote: RemoteSyncState,
        local_changed: bool,
        remote_changed: bool,
    ) -> SyncDecision | None:
        if remote.deleted and not local.deleted:
            if local_changed and direction is SyncDirection.BIDIRECTIONAL:
                return SyncDecision(
                    SyncItemOperation.CONFLICT,
                    conflict_type=(
                        SyncConflictType.REMOTE_DELETED_LOCAL_MODIFIED
                    ),
                    reason="Remote was deleted while local content changed.",
                )
            return SyncDecision(
                SyncItemOperation.REMOTE_DELETE_DETECTED,
                reason="Remote deletion detected.",
            )
        if local.deleted and not remote.deleted:
            if remote_changed and direction is SyncDirection.BIDIRECTIONAL:
                return SyncDecision(
                    SyncItemOperation.CONFLICT,
                    conflict_type=(
                        SyncConflictType.LOCAL_DELETED_REMOTE_MODIFIED
                    ),
                    reason="Local was deleted while remote content changed.",
                )
            return SyncDecision(
                SyncItemOperation.LOCAL_DELETE_DETECTED,
                reason="Local deletion detected.",
            )
        if local.deleted and remote.deleted:
            return SyncDecision(
                SyncItemOperation.SKIP,
                reason="Both sides are deleted.",
            )
        return None

    @staticmethod
    def _resolve_both_modified(
        *,
        conflict_policy: ConflictPolicy,
        local: LocalSyncState,
        remote: RemoteSyncState,
    ) -> SyncDecision:
        if conflict_policy is ConflictPolicy.APPLICATION_WINS:
            return SyncDecision(
                SyncItemOperation.UPDATE_REMOTE,
                reason="Application-wins policy selected local content.",
            )
        if conflict_policy is ConflictPolicy.SHAREPOINT_WINS:
            return SyncDecision(
                SyncItemOperation.UPDATE_LOCAL,
                reason="SharePoint-wins policy selected remote content.",
            )
        if conflict_policy is ConflictPolicy.CREATE_COPY:
            return SyncDecision(
                SyncItemOperation.CREATE_REMOTE,
                reason="Create-copy policy preserves both versions.",
                create_copy=True,
            )
        if conflict_policy is ConflictPolicy.LATEST_MODIFIED_WINS:
            local_time = SharePointSyncEngine._utc_min(local.modified_at)
            remote_time = SharePointSyncEngine._utc_min(remote.modified_at)
            if local_time > remote_time:
                return SyncDecision(
                    SyncItemOperation.UPDATE_REMOTE,
                    reason="Local content has the later modification time.",
                )
            if remote_time > local_time:
                return SyncDecision(
                    SyncItemOperation.UPDATE_LOCAL,
                    reason="Remote content has the later modification time.",
                )
        return SyncDecision(
            SyncItemOperation.CONFLICT,
            conflict_type=SyncConflictType.BOTH_MODIFIED,
            reason="Both sides changed and require manual resolution.",
        )

    @staticmethod
    def _utc_min(value: datetime | None) -> datetime:
        if value is None:
            return datetime.min.replace(tzinfo=UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
